import hashlib
import hmac
import json
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from sqlmodel import select, func, or_, col
from sqlmodel.ext.asyncio.session import AsyncSession

from src.config import ENVIRONMENT_SETTINGS
from src.connections.databases.db import Player, Membership, PaymentRecord, MembershipType
from src.modules.v1.schemas.dtos import AddMembershipRequest
from src.modules.v1.services.memberships_service import MembershipsService
from src.modules.v1.services.membership_types_service import MembershipTypesService

logger = logging.getLogger("wardogs.tebex")


class TebexWebhookService:

    @staticmethod
    def verify_signature(raw_body: bytes, header_signature: Optional[str]) -> bool:
        """
        Validates the incoming signature header against the raw request body.
        Supports both:
        1. Tebex official spec: HMAC-SHA256(secret, sha256(raw_body).hexdigest())
        2. Fallback: HMAC-SHA256(secret, raw_body)
        """
        secret = ENVIRONMENT_SETTINGS.SECURITY_SETTINGS.TEBEX_WEBHOOK_SECRET
        if not secret:
            logger.warning("[Tebex] TEBEX_WEBHOOK_SECRET is not configured. Skipping signature check.")
            return True

        if not header_signature:
            logger.warning("[Tebex] Missing webhook signature header.")
            return False

        clean_header = header_signature.strip()

        # 1. Tebex official specification: hash raw body with sha256 first
        body_sha256 = hashlib.sha256(raw_body).hexdigest()
        computed_official = hmac.new(
            secret.encode("utf-8"),
            body_sha256.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        if hmac.compare_digest(computed_official, clean_header):
            return True

        # 2. Fallback: direct HMAC over raw_body
        computed_direct = hmac.new(
            secret.encode("utf-8"),
            raw_body,
            hashlib.sha256
        ).hexdigest()
        if hmac.compare_digest(computed_direct, clean_header):
            return True

        logger.warning("[Tebex] Invalid webhook signature detected.")
        return False

    @staticmethod
    def extract_buyer_identifiers(subject: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extracts (steam_id, discord_id, username) from Tebex subject structure.
        Inspects:
        - customer.username (id/username)
        - products[].username (id/username)
        - products[].variables / options (identifiers matching steam / discord)
        - subject.custom / products[].custom
        """
        steam_id: Optional[str] = None
        discord_id: Optional[str] = None
        username: Optional[str] = None

        def clean_val(v: Any) -> str:
            return str(v).strip() if v is not None else ""

        # 1. Customer level inspection
        customer = subject.get("customer") or {}
        c_user = customer.get("username")
        if isinstance(c_user, dict):
            c_uid = clean_val(c_user.get("id"))
            c_uname = clean_val(c_user.get("username"))
            if c_uid.isdigit():
                if len(c_uid) == 17 and c_uid.startswith("7656119"):
                    steam_id = c_uid
                elif 17 <= len(c_uid) <= 20:
                    discord_id = c_uid
            if c_uname:
                username = c_uname
        elif isinstance(c_user, str) and c_user.strip():
            u_clean = c_user.strip()
            if u_clean.isdigit():
                if len(u_clean) == 17 and u_clean.startswith("7656119"):
                    steam_id = u_clean
                elif 17 <= len(u_clean) <= 20:
                    discord_id = u_clean
            else:
                username = u_clean

        if not username:
            first_name = clean_val(customer.get("first_name"))
            if first_name and first_name.lower() != "test":
                username = first_name

        # 2. Product level inspection
        products = subject.get("products") or []
        for p in products:
            if not isinstance(p, dict):
                continue

            # Product username
            p_user = p.get("username")
            if isinstance(p_user, dict):
                p_uid = clean_val(p_user.get("id"))
                if p_uid.isdigit() and len(p_uid) == 17 and p_uid.startswith("7656119") and not steam_id:
                    steam_id = p_uid
                if not username and p_user.get("username"):
                    username = clean_val(p_user.get("username"))

            # Product variables
            p_vars = p.get("variables")
            if isinstance(p_vars, list):
                for v in p_vars:
                    if not isinstance(v, dict):
                        continue
                    ident = clean_val(v.get("identifier")).lower()
                    opt = clean_val(v.get("option"))
                    if not opt:
                        continue
                    if (opt.isdigit() and len(opt) == 17 and opt.startswith("7656119")) or ("steam" in ident and opt.isdigit() and len(opt) == 17):
                        steam_id = opt
                    elif (opt.isdigit() and 17 <= len(opt) <= 20 and not opt.startswith("7656119")) or ("discord" in ident and opt.isdigit() and 17 <= len(opt) <= 20):
                        discord_id = opt
            elif isinstance(p_vars, dict):
                for k, v in p_vars.items():
                    k_lower = clean_val(k).lower()
                    v_str = clean_val(v)
                    if not v_str:
                        continue
                    if (v_str.isdigit() and len(v_str) == 17 and v_str.startswith("7656119")) or ("steam" in k_lower and v_str.isdigit() and len(v_str) == 17):
                        steam_id = v_str
                    elif (v_str.isdigit() and 17 <= len(v_str) <= 20 and not v_str.startswith("7656119")) or ("discord" in k_lower and v_str.isdigit() and 17 <= len(v_str) <= 20):
                        discord_id = v_str

            # Product custom options
            p_custom = p.get("custom")
            if isinstance(p_custom, dict):
                for k, v in p_custom.items():
                    k_lower = clean_val(k).lower()
                    v_str = clean_val(v)
                    if not v_str:
                        continue
                    if "steam" in k_lower and v_str.isdigit() and len(v_str) == 17:
                        steam_id = v_str
                    elif "discord" in k_lower and v_str.isdigit() and 17 <= len(v_str) <= 20:
                        discord_id = v_str

        # 3. Subject-level custom fields
        s_custom = subject.get("custom")
        if isinstance(s_custom, dict):
            for k, v in s_custom.items():
                k_lower = clean_val(k).lower()
                v_str = clean_val(v)
                if not v_str:
                    continue
                if "steam" in k_lower and not steam_id and v_str.isdigit() and len(v_str) == 17:
                    steam_id = v_str
                elif "discord" in k_lower and not discord_id and v_str.isdigit() and 17 <= len(v_str) <= 20:
                    discord_id = v_str

        # If steam_id still not found, check if username is a valid Steam64 ID
        if not steam_id and username and username.isdigit() and len(username) == 17 and username.startswith("7656119"):
            steam_id = username

        return steam_id, discord_id, username

    @staticmethod
    async def resolve_membership_type(
        product: Dict[str, Any],
        session: AsyncSession
    ) -> Optional[MembershipType]:
        """
        Finds the matching MembershipType in database by:
        1. Tebex package ID (`tebex_package_id`)
        2. Exact code or name match
        3. Name substring match (e.g. EXPRESS -> VIP_EXPRESS, COMUN -> VIP_COMUN)
        4. Fallback to first active membership type
        """
        await MembershipTypesService._ensure_defaults(session)

        pkg_id = product.get("id")
        if pkg_id:
            try:
                pkg_int = int(pkg_id)
                m_type = (await session.exec(
                    select(MembershipType).where(MembershipType.tebex_package_id == pkg_int)
                )).first()
                if m_type:
                    return m_type
            except (ValueError, TypeError):
                pass

        pkg_name = str(product.get("name", "")).strip().upper()
        if pkg_name:
            norm_name = pkg_name.replace(" ", "_")
            m_type = (await session.exec(
                select(MembershipType).where(
                    or_(
                        func.upper(MembershipType.code) == norm_name,
                        func.upper(MembershipType.name) == pkg_name
                    )
                )
            )).first()
            if m_type:
                return m_type

            # Substring matching
            if "EXPRESS" in pkg_name:
                m_type = (await session.exec(
                    select(MembershipType).where(MembershipType.code == "VIP_EXPRESS")
                )).first()
                if m_type:
                    return m_type

            if "COMUN" in pkg_name or "COMMON" in pkg_name:
                m_type = (await session.exec(
                    select(MembershipType).where(MembershipType.code == "VIP_COMUN")
                )).first()
                if m_type:
                    return m_type

        # Default fallback
        return (await session.exec(
            select(MembershipType).where(MembershipType.is_active == True).order_by(col(MembershipType.id))
        )).first()

    @staticmethod
    async def handle_webhook(
        payload: Dict[str, Any],
        raw_payload_str: str,
        session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Dispatches the parsed Tebex webhook event to the appropriate handler.
        """
        event_type = payload.get("type", "")
        event_id = payload.get("id", "")

        # 1. Tebex Endpoint Handshake / Validation Event
        if event_type == "validation.webhook":
            logger.info(f"[Tebex] Responding to validation handshake for event ID: {event_id}")
            return {"id": event_id}

        logger.info(f"[Tebex] Received webhook event: {event_type} (ID: {event_id})")

        # 2. Payment Completed (New Purchase)
        if event_type == "payment.completed":
            return await TebexWebhookService.process_payment_completed(payload, raw_payload_str, session)

        # 3. Recurring Payment Started
        if event_type in ("recurring-payment.started", "recurring-payment-started"):
            return await TebexWebhookService.process_recurring_started(payload, raw_payload_str, session)

        # 4. Recurring Payment Renewed
        if event_type == "recurring-payment.renewed":
            return await TebexWebhookService.process_recurring_renewed(payload, raw_payload_str, session)

        # 5. Recurring Payment Ended / Cancelled
        if event_type in ("recurring-payment.ended", "recurring-payment.cancellation.requested"):
            return await TebexWebhookService.process_recurring_ended(payload, raw_payload_str, session)

        # 6. Recurring Payment Status Changed
        if event_type in ("recurring-payment.status.changed", "recurring-payment.status-changed"):
            return await TebexWebhookService.process_recurring_status_changed(payload, raw_payload_str, session)

        # 7. Payment Refunded / Dispute Lost
        if event_type in ("payment.refunded", "payment.dispute.lost"):
            return await TebexWebhookService.process_payment_refunded(payload, raw_payload_str, session)

        # Unhandled / Informational events (e.g. payment.declined, basket.abandoned)
        return {
            "status": "ignored",
            "event": event_type,
            "id": event_id
        }

    @staticmethod
    async def process_payment_completed(
        payload: Dict[str, Any],
        raw_payload_str: str,
        session: AsyncSession
    ) -> Dict[str, Any]:
        subject = payload.get("subject") or {}
        transaction_id = str(subject.get("transaction_id") or payload.get("id") or "").strip()

        if not transaction_id:
            return {"status": "error", "message": "Missing transaction_id"}

        # Idempotency check: don't double-grant
        existing_record = (await session.exec(
            select(PaymentRecord).where(PaymentRecord.transaction_id == transaction_id)
        )).first()
        if existing_record and existing_record.status == "COMPLETED":
            logger.info(f"[Tebex] Transaction {transaction_id} already processed. Skipping duplicate.")
            return {
                "status": "already_processed",
                "transaction_id": transaction_id,
                "event": "payment.completed"
            }

        # Extract identifiers
        steam_id, discord_id, username = TebexWebhookService.extract_buyer_identifiers(subject)
        if not steam_id:
            logger.error(f"[Tebex] Could not extract steam_id from payment {transaction_id}.")
            record = PaymentRecord(
                transaction_id=transaction_id,
                event_type="payment.completed",
                discord_id=discord_id,
                status="IGNORED",
                raw_payload=raw_payload_str
            )
            session.add(record)
            await session.commit()
            return {
                "status": "ignored",
                "reason": "Missing steam_id",
                "transaction_id": transaction_id
            }

        # 1. Resolve or create Player
        player = await session.get(Player, steam_id)
        if not player:
            player = Player(
                steam_id=steam_id,
                discord_id=discord_id,
                in_game_name=username or f"Player_{steam_id[-4:]}"
            )
            session.add(player)
            await session.commit()
            await session.refresh(player)
        else:
            updated = False
            if discord_id and player.discord_id != discord_id:
                # Handle unique constraint: unlink if assigned to a different steam_id
                conflict = (await session.exec(select(Player).where(Player.discord_id == discord_id))).first()
                if conflict and conflict.steam_id != player.steam_id:
                    conflict.discord_id = None
                    session.add(conflict)
                player.discord_id = discord_id
                updated = True
            if username and not player.in_game_name:
                player.in_game_name = username
                updated = True
            if updated:
                session.add(player)
                await session.commit()

        # 2. Resolve package & membership type
        products = subject.get("products") or []
        first_product = products[0] if products else {}
        m_type = await TebexWebhookService.resolve_membership_type(first_product, session)

        membership_type_code = m_type.code if m_type else "VIP_COMUN"
        days_to_add = m_type.default_days if m_type else 30
        sub_ref = subject.get("recurring_payment_reference")

        # 3. Create or extend membership
        add_req = AddMembershipRequest(
            steam_id=steam_id,
            membership_type=membership_type_code,
            days=days_to_add,
            tebex_transaction_id=transaction_id,
            tebex_subscription_id=sub_ref,
            payment_source="TEBEX",
            server_id=m_type.server_id if m_type else None
        )
        await MembershipsService.add_membership(add_req, session)

        # 4. Sync RCON slots immediately
        try:
            await MembershipsService.sync_memberships_logic(session)
        except Exception as sync_err:
            logger.warning(f"[Tebex] RCON sync notice: {sync_err}")

        # 5. Record PaymentRecord
        price_info = subject.get("price") or subject.get("price_paid") or {}
        amount = float(price_info.get("amount", 0.0))
        currency = str(price_info.get("currency", "USD"))
        pkg_id = first_product.get("id")
        pkg_name = first_product.get("name") or membership_type_code

        if existing_record:
            existing_record.status = "COMPLETED"
            existing_record.steam_id = steam_id
            existing_record.discord_id = discord_id
            existing_record.package_id = pkg_id
            existing_record.package_name = pkg_name
            existing_record.amount = amount
            existing_record.currency = currency
            existing_record.raw_payload = raw_payload_str
            session.add(existing_record)
        else:
            record = PaymentRecord(
                transaction_id=transaction_id,
                event_type="payment.completed",
                steam_id=steam_id,
                discord_id=discord_id,
                package_id=pkg_id,
                package_name=pkg_name,
                amount=amount,
                currency=currency,
                status="COMPLETED",
                raw_payload=raw_payload_str
            )
            session.add(record)
        await session.commit()

        return {
            "status": "success",
            "event": "payment.completed",
            "transaction_id": transaction_id,
            "steam_id": steam_id,
            "membership_type": membership_type_code,
            "days": days_to_add
        }

    @staticmethod
    async def process_recurring_started(
        payload: Dict[str, Any],
        raw_payload_str: str,
        session: AsyncSession
    ) -> Dict[str, Any]:
        subject = payload.get("subject") or {}
        ref = str(subject.get("reference") or "").strip()
        initial_payment = subject.get("initial_payment") or {}
        tx_id = str(initial_payment.get("transaction_id") or payload.get("id") or f"start-{ref}").strip()
        target_tx_id = f"start-{ref}-{tx_id}"

        # Idempotency check: don't double-process duplicate webhook
        existing_record = (await session.exec(
            select(PaymentRecord).where(PaymentRecord.transaction_id == target_tx_id)
        )).first()
        if existing_record:
            logger.info(f"[Tebex] Recurring started {target_tx_id} already processed. Skipping duplicate.")
            return {
                "status": "already_processed",
                "event": "recurring-payment.started",
                "subscription_ref": ref,
                "transaction_id": target_tx_id
            }

        # Check if membership already exists (from payment.completed)
        membership = None
        if ref:
            membership = (await session.exec(
                select(Membership).where(
                    Membership.tebex_subscription_id == ref,
                    Membership.is_active == True
                )
            )).first()

        steam_id, discord_id, _ = TebexWebhookService.extract_buyer_identifiers(initial_payment or subject)
        if not membership and tx_id:
            membership = (await session.exec(
                select(Membership).where(
                    Membership.tebex_transaction_id == tx_id,
                    Membership.is_active == True
                )
            )).first()

        if membership:
            if ref and not membership.tebex_subscription_id:
                membership.tebex_subscription_id = ref
                session.add(membership)
                await session.commit()
        elif initial_payment:
            # Handle possible out-of-order delivery where recurring-payment.started arrives first
            synthetic_payload = {
                "id": str(payload.get("id")),
                "type": "payment.completed",
                "subject": {
                    **initial_payment,
                    "recurring_payment_reference": ref
                }
            }
            return await TebexWebhookService.process_payment_completed(
                synthetic_payload, raw_payload_str, session
            )

        # Audit record
        price_info = subject.get("price") or initial_payment.get("price") or {}
        record = PaymentRecord(
            transaction_id=f"start-{ref}-{tx_id}",
            event_type="recurring-payment.started",
            steam_id=steam_id or (membership.steam_id if membership else None),
            discord_id=discord_id,
            amount=float(price_info.get("amount", 0.0)),
            currency=str(price_info.get("currency", "USD")),
            status="COMPLETED",
            raw_payload=raw_payload_str
        )
        session.add(record)
        await session.commit()

        return {
            "status": "success",
            "event": "recurring-payment.started",
            "subscription_ref": ref
        }

    @staticmethod
    async def process_recurring_renewed(
        payload: Dict[str, Any],
        raw_payload_str: str,
        session: AsyncSession
    ) -> Dict[str, Any]:
        subject = payload.get("subject") or {}
        ref = str(subject.get("reference") or "").strip()
        last_payment = subject.get("last_payment") or {}
        raw_tx_id = str(last_payment.get("transaction_id") or payload.get("id") or f"renew-{ref}").strip()
        event_id = str(payload.get("id") or "").strip()
        prefixed_tx_id = f"renew-{raw_tx_id}-{event_id}" if event_id else f"renew-{raw_tx_id}"

        # Idempotency check: see if this exact renewal has already been handled
        existing_renewal = (await session.exec(
            select(PaymentRecord).where(
                or_(
                    PaymentRecord.transaction_id == prefixed_tx_id,
                    (PaymentRecord.transaction_id == raw_tx_id) & (PaymentRecord.status == "RENEWED")
                )
            )
        )).first()
        if existing_renewal and existing_renewal.status == "RENEWED":
            return {"status": "already_processed", "transaction_id": existing_renewal.transaction_id}

        # Check if raw_tx_id is already taken by another record (e.g. initial payment.completed)
        existing_any = (await session.exec(
            select(PaymentRecord).where(PaymentRecord.transaction_id == raw_tx_id)
        )).first()
        target_tx_id = prefixed_tx_id if existing_any else raw_tx_id

        # Locate membership
        membership = None
        if ref:
            membership = (await session.exec(
                select(Membership)
                .where(Membership.tebex_subscription_id == ref)
                .order_by(col(Membership.is_active).desc(), col(Membership.id).desc())
            )).first()

        steam_id, discord_id, _ = TebexWebhookService.extract_buyer_identifiers(last_payment or subject)
        if not membership and steam_id:
            membership = (await session.exec(
                select(Membership)
                .where(Membership.steam_id == steam_id)
                .order_by(col(Membership.is_active).desc(), col(Membership.id).desc())
            )).first()

        days_added = 30
        if membership:
            norm_type = membership.membership_type.upper()
            m_type = (await session.exec(select(MembershipType).where(func.upper(MembershipType.code) == norm_type))).first()
            days_added = m_type.default_days if m_type and m_type.default_days > 0 else 30

            now_utc = datetime.now(timezone.utc)
            m_end = membership.end_time
            if m_end is not None:
                if m_end.tzinfo is None:
                    m_end = m_end.replace(tzinfo=timezone.utc)
                if m_end > now_utc:
                    membership.end_time = m_end + timedelta(days=days_added)
                else:
                    membership.end_time = now_utc + timedelta(days=days_added)
            else:
                membership.end_time = now_utc + timedelta(days=days_added)
            membership.is_active = True
            if membership.role_granted_id:
                vip_pr = (await session.exec(select(PlayerRole).where(
                    PlayerRole.steam_id == membership.steam_id,
                    PlayerRole.role_id == membership.role_granted_id
                ))).first()
                if not vip_pr:
                    session.add(PlayerRole(steam_id=membership.steam_id, role_id=membership.role_granted_id))
            if membership.special_role_id:
                sp_pr = (await session.exec(select(PlayerRole).where(
                    PlayerRole.steam_id == membership.steam_id,
                    PlayerRole.role_id == membership.special_role_id
                ))).first()
                if not sp_pr:
                    session.add(PlayerRole(steam_id=membership.steam_id, role_id=membership.special_role_id))
            session.add(membership)
            await session.commit()

            try:
                await MembershipsService.sync_memberships_logic(session)
            except Exception as sync_err:
                logger.warning(f"[Tebex] RCON sync notice during renewal: {sync_err}")

        price_info = subject.get("price") or last_payment.get("price") or {}
        record = PaymentRecord(
            transaction_id=target_tx_id,
            event_type="recurring-payment.renewed",
            steam_id=steam_id or (membership.steam_id if membership else None),
            discord_id=discord_id,
            amount=float(price_info.get("amount", 0.0)),
            currency=str(price_info.get("currency", "USD")),
            status="RENEWED",
            raw_payload=raw_payload_str
        )
        session.add(record)
        await session.commit()

        return {
            "status": "success",
            "event": "recurring-payment.renewed",
            "subscription_ref": ref,
            "days_added": days_added,
            "transaction_id": target_tx_id
        }

    @staticmethod
    async def process_recurring_ended(
        payload: Dict[str, Any],
        raw_payload_str: str,
        session: AsyncSession
    ) -> Dict[str, Any]:
        subject = payload.get("subject") or {}
        ref = str(subject.get("reference") or "").strip()
        event_type = payload.get("type", "recurring-payment.ended")
        target_tx_id = f"end-{ref}-{payload.get('id', '')}"

        # Idempotency check
        existing_record = (await session.exec(
            select(PaymentRecord).where(PaymentRecord.transaction_id == target_tx_id)
        )).first()
        if existing_record:
            logger.info(f"[Tebex] Recurring ended {target_tx_id} already processed. Skipping duplicate.")
            return {
                "status": "already_processed",
                "event": event_type,
                "reference": ref,
                "transaction_id": target_tx_id
            }

        # Revoke or update active membership associated with this subscription reference
        revoked_count = 0
        if ref:
            stmt = select(Membership).where(
                Membership.tebex_subscription_id == ref,
                Membership.is_active == True
            )
            memberships = (await session.exec(stmt)).all()
            now = datetime.now(timezone.utc)
            for m in memberships:
                # If end_time is in the future, the user already paid for this cycle!
                # Do NOT deactivate immediately; let it expire naturally at end_time.
                # Unlink subscription reference so renewals stop.
                if m.end_time and (m.end_time if m.end_time.tzinfo else m.end_time.replace(tzinfo=timezone.utc)) > now:
                    # User already prepaid for this billing cycle; keep active until natural expiry at end_time.
                    # Keep m.tebex_subscription_id intact for audit history.
                    pass
                else:
                    await MembershipsService._deactivate_membership(m, session, revoke_special_role=False)
                    revoked_count += 1
            if memberships:
                await session.commit()
                try:
                    await MembershipsService.sync_memberships_logic(session)
                except Exception as e:
                    logger.warning(f"[Tebex] RCON sync after recurring ended error: {e}")

        record = PaymentRecord(
            transaction_id=target_tx_id,
            event_type=event_type,
            status="CANCELLED",
            raw_payload=raw_payload_str
        )
        session.add(record)
        await session.commit()

        return {
            "status": "success",
            "event": event_type,
            "reference": ref,
            "revoked_count": revoked_count
        }

    @staticmethod
    async def process_recurring_status_changed(
        payload: Dict[str, Any],
        raw_payload_str: str,
        session: AsyncSession
    ) -> Dict[str, Any]:
        subject = payload.get("subject") or {}
        ref = str(subject.get("reference") or "").strip()
        status_info = subject.get("status") or {}
        status_id = status_info.get("id")
        status_desc = str(status_info.get("description", ""))

        # Tebex Status IDs: 4 = Expired, 5 = Cancelled
        if status_id in (4, 5) or status_desc.lower() in ("expired", "cancelled"):
            return await TebexWebhookService.process_recurring_ended(payload, raw_payload_str, session)

        target_tx_id = f"status-{ref}-{payload.get('id', '')}"
        existing_record = (await session.exec(
            select(PaymentRecord).where(PaymentRecord.transaction_id == target_tx_id)
        )).first()
        if existing_record:
            logger.info(f"[Tebex] Recurring status changed {target_tx_id} already processed. Skipping duplicate.")
            return {
                "status": "already_processed",
                "event": "recurring-payment.status.changed",
                "reference": ref,
                "transaction_id": target_tx_id
            }

        record = PaymentRecord(
            transaction_id=target_tx_id,
            event_type="recurring-payment.status.changed",
            status=f"STATUS_{status_id or status_desc.upper()}",
            raw_payload=raw_payload_str
        )
        session.add(record)
        await session.commit()

        return {
            "status": "success",
            "event": "recurring-payment.status.changed",
            "reference": ref,
            "status_id": status_id,
            "description": status_desc
        }

    @staticmethod
    async def process_payment_refunded(
        payload: Dict[str, Any],
        raw_payload_str: str,
        session: AsyncSession
    ) -> Dict[str, Any]:
        subject = payload.get("subject") or {}
        transaction_id = str(subject.get("transaction_id") or payload.get("id") or "").strip()
        event_type = payload.get("type", "payment.refunded")
        target_tx_id = f"refund-{transaction_id}-{payload.get('id', '')}"

        # Idempotency check
        existing_record = (await session.exec(
            select(PaymentRecord).where(PaymentRecord.transaction_id == target_tx_id)
        )).first()
        if existing_record:
            logger.info(f"[Tebex] Refund {target_tx_id} already processed. Skipping duplicate.")
            return {
                "status": "already_processed",
                "event": event_type,
                "transaction_id": target_tx_id
            }

        steam_id, discord_id, _ = TebexWebhookService.extract_buyer_identifiers(subject)

        # Deactivate any active memberships linked to this transaction or steam_id
        revoked_memberships = []
        if transaction_id:
            stmt = select(Membership).where(Membership.is_active == True, Membership.tebex_transaction_id == transaction_id)
            revoked_memberships = list((await session.exec(stmt)).all())

        if not revoked_memberships and steam_id:
            stmt = select(Membership).where(Membership.is_active == True, Membership.steam_id == steam_id)
            revoked_memberships = list((await session.exec(stmt)).all())
        for m in revoked_memberships:
            await MembershipsService._deactivate_membership(m, session, revoke_special_role=True)
        await session.commit()

        # Immediately revoke reserved slot via RCON sync
        try:
            await MembershipsService.sync_memberships_logic(session)
        except Exception as e:
            logger.warning(f"[Tebex] RCON sync after refund error: {e}")

        record = PaymentRecord(
            transaction_id=target_tx_id,
            event_type=event_type,
            steam_id=steam_id,
            discord_id=discord_id,
            status="REFUNDED",
            raw_payload=raw_payload_str
        )
        session.add(record)
        await session.commit()

        return {
            "status": "success",
            "event": event_type,
            "revoked_count": len(revoked_memberships)
        }
