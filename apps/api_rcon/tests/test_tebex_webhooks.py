import hmac
import hashlib
import json
import pytest
from datetime import datetime, timezone, timedelta
from sqlmodel import select

from src.config import ENVIRONMENT_SETTINGS
from src.connections.databases.db import Player, Membership, PaymentRecord, MembershipType
from src.modules.v1.services.membership_types_service import MembershipTypesService


def generate_tebex_signature(secret: str, raw_body: bytes, use_official_spec: bool = True) -> str:
    if use_official_spec:
        body_hash = hashlib.sha256(raw_body).hexdigest()
        return hmac.new(secret.encode("utf-8"), body_hash.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_tebex_webhook_validation_handshake(client):
    """Tebex validation.webhook event must return the same id with 200 OK."""
    payload = {
        "id": "validation-event-999888",
        "type": "validation.webhook",
        "date": "2026-09-22T13:00:00Z",
        "subject": {}
    }
    resp = await client.post("/api/v1/webhooks/tebex", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"id": "validation-event-999888"}


@pytest.mark.asyncio
async def test_tebex_webhook_hmac_signature_verification(client, monkeypatch):
    """Verifies that HMAC-SHA256 signatures are correctly enforced when TEBEX_WEBHOOK_SECRET is set."""
    secret = "my_super_secret_webhook_key"
    monkeypatch.setattr(ENVIRONMENT_SETTINGS.SECURITY_SETTINGS, "TEBEX_WEBHOOK_SECRET", secret)

    payload = {
        "id": "event-1234",
        "type": "payment.completed",
        "subject": {
            "transaction_id": "tx_sig_test",
            "customer": {
                "username": {"id": "76561198000000001", "username": "TestGamer"}
            },
            "products": [
                {
                    "id": 7682027,
                    "name": "VIP COMUN",
                    "variables": [{"identifier": "discord_id", "option": "112233445566778899"}]
                }
            ],
            "price": {"amount": 6.0, "currency": "USD"}
        }
    }
    raw_bytes = json.dumps(payload).encode("utf-8")

    # 1. Missing header -> 401
    resp = await client.post(
        "/api/v1/webhooks/tebex",
        content=raw_bytes,
        headers={"Content-Type": "application/json"}
    )
    assert resp.status_code == 401
    assert "Invalid X-Tebex-Signature" in resp.json()["detail"]

    # 2. Invalid header -> 401
    resp = await client.post(
        "/api/v1/webhooks/tebex",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Tebex-Signature": "invalid_signature"}
    )
    assert resp.status_code == 401

    # 3. Valid official Tebex HMAC (X-Signature) -> 200
    official_sig = generate_tebex_signature(secret, raw_bytes, use_official_spec=True)
    resp = await client.post(
        "/api/v1/webhooks/tebex",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Signature": official_sig}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    assert resp.json()["event"] == "payment.completed"


@pytest.mark.asyncio
async def test_tebex_webhook_invalid_json(client):
    """Invalid JSON body should return 400."""
    resp = await client.post(
        "/api/v1/webhooks/tebex",
        content=b"not a valid json",
        headers={"Content-Type": "application/json"}
    )
    assert resp.status_code == 400
    assert "Invalid JSON payload" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_tebex_payment_completed_full_lifecycle(client, session):
    """
    Tests full payment.completed event:
    1. Player auto-creation
    2. Discord ID auto-linking
    3. Membership creation with Tebex transaction ID & source
    4. PaymentRecord saved
    5. Idempotency on duplicate POST
    """
    steam_id = "76561198099999999"
    discord_id = "987654321098765432"
    tx_id = "tbx-tx-990011"

    payload = {
        "id": "evt-payment-complete-1",
        "type": "payment.completed",
        "date": "2026-09-22T14:00:00Z",
        "subject": {
            "transaction_id": tx_id,
            "status": {"id": 1, "description": "Complete"},
            "payment_sequence": "oneoff",
            "price": {"amount": 6.00, "currency": "USD"},
            "customer": {
                "first_name": "TebexBuyer",
                "username": {"id": steam_id, "username": "TebexBuyer"}
            },
            "products": [
                {
                    "id": 7682027,
                    "name": "VIP COMUN",
                    "variables": [
                        {"identifier": "discord_id", "option": discord_id}
                    ]
                }
            ]
        }
    }

    # 1. First POST: should succeed and create Player & Membership
    resp = await client.post("/api/v1/webhooks/tebex", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["transaction_id"] == tx_id
    assert data["steam_id"] == steam_id
    assert data["membership_type"] == "VIP_COMUN"
    assert data["days"] == 30

    # Verify Player in DB
    player = await session.get(Player, steam_id)
    assert player is not None
    assert player.steam_id == steam_id
    assert player.discord_id == discord_id
    assert player.in_game_name == "TebexBuyer"

    # Verify Membership in DB
    m = (await session.exec(
        select(Membership).where(
            Membership.steam_id == steam_id,
            Membership.is_active == True
        )
    )).first()
    assert m is not None
    assert m.membership_type == "VIP_COMUN"
    assert m.tebex_transaction_id == tx_id
    assert m.payment_source == "TEBEX"
    assert m.end_time is not None

    # Verify PaymentRecord in DB
    pr = (await session.exec(
        select(PaymentRecord).where(PaymentRecord.transaction_id == tx_id)
    )).first()
    assert pr is not None
    assert pr.status == "COMPLETED"
    assert pr.amount == 6.00
    assert pr.currency == "USD"
    assert pr.package_id == 7682027

    # 2. Duplicate POST: should detect idempotency and NOT duplicate
    resp_dup = await client.post("/api/v1/webhooks/tebex", json=payload)
    assert resp_dup.status_code == 200
    dup_data = resp_dup.json()
    assert dup_data["status"] == "already_processed"
    assert dup_data["transaction_id"] == tx_id

    # Verify still only 1 active membership
    memberships = (await session.exec(
        select(Membership).where(
            Membership.steam_id == steam_id,
            Membership.is_active == True
        )
    )).all()
    assert len(memberships) == 1


@pytest.mark.asyncio
async def test_tebex_recurring_payment_renewed(client, session):
    """
    Tests recurring-payment.renewed extending the expiration date of an active membership.
    """
    steam_id = "76561198088888888"
    sub_ref = "tbx-sub-recurring-88"

    # Setup player and active membership
    player = Player(steam_id=steam_id, in_game_name="RenewPlayer")
    session.add(player)
    await session.commit()

    initial_end = datetime.now(timezone.utc) + timedelta(days=5)
    membership = Membership(
        steam_id=steam_id,
        membership_type="VIP_COMUN",
        start_time=datetime.now(timezone.utc) - timedelta(days=25),
        end_time=initial_end,
        is_active=True,
        tebex_subscription_id=sub_ref,
        payment_source="TEBEX"
    )
    session.add(membership)
    await session.commit()
    await session.refresh(membership)

    payload = {
        "id": "evt-renew-1",
        "type": "recurring-payment.renewed",
        "subject": {
            "reference": sub_ref,
            "status": {"id": 2, "description": "Active"},
            "price": {"amount": 6.00, "currency": "USD"},
            "last_payment": {
                "transaction_id": "tx-renew-101",
                "customer": {
                    "username": {"id": steam_id}
                }
            }
        }
    }

    resp = await client.post("/api/v1/webhooks/tebex", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["event"] == "recurring-payment.renewed"

    # Verify extended end_time
    await session.refresh(membership)
    assert membership.end_time is not None
    m_end = membership.end_time
    if m_end.tzinfo is None:
        m_end = m_end.replace(tzinfo=timezone.utc)
    assert m_end > initial_end + timedelta(days=28)

    # Verify PaymentRecord
    pr = (await session.exec(
        select(PaymentRecord).where(PaymentRecord.transaction_id == "tx-renew-101")
    )).first()
    assert pr is not None
    assert pr.status == "RENEWED"


@pytest.mark.asyncio
async def test_tebex_payment_refunded_revocation(client, session):
    """
    Tests payment.refunded revoking the active membership immediately.
    """
    steam_id = "76561198077777777"
    tx_id = "tx-refund-target-77"

    player = Player(steam_id=steam_id, in_game_name="RefundPlayer")
    session.add(player)
    await session.commit()

    membership = Membership(
        steam_id=steam_id,
        membership_type="VIP_EXPRESS",
        is_active=True,
        tebex_transaction_id=tx_id,
        payment_source="TEBEX"
    )
    session.add(membership)
    await session.commit()
    await session.refresh(membership)

    payload = {
        "id": "evt-refund-1",
        "type": "payment.refunded",
        "subject": {
            "transaction_id": tx_id,
            "customer": {
                "username": {"id": steam_id}
            }
        }
    }

    resp = await client.post("/api/v1/webhooks/tebex", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["revoked_count"] == 1

    # Verify membership deactivated
    await session.refresh(membership)
    assert membership.is_active is False


@pytest.mark.asyncio
async def test_tebex_recurring_payment_started(client, session):
    """
    Tests recurring-payment.started links the subscription reference to the active membership.
    """
    steam_id = "76561198066666666"
    tx_id = "tx-initial-66"
    sub_ref = "sub-agreement-66"

    player = Player(steam_id=steam_id, in_game_name="SubStartPlayer")
    session.add(player)
    await session.commit()

    membership = Membership(
        steam_id=steam_id,
        membership_type="VIP_COMUN",
        is_active=True,
        tebex_transaction_id=tx_id,
        payment_source="TEBEX"
    )
    session.add(membership)
    await session.commit()
    await session.refresh(membership)

    payload = {
        "id": "evt-sub-start-1",
        "type": "recurring-payment.started",
        "subject": {
            "reference": sub_ref,
            "status": {"id": 2, "description": "Active"},
            "price": {"amount": 6.00, "currency": "USD"},
            "initial_payment": {
                "transaction_id": tx_id,
                "customer": {"username": {"id": steam_id}}
            }
        }
    }

    resp = await client.post("/api/v1/webhooks/tebex", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["subscription_ref"] == sub_ref

    # Verify subscription id linked to membership
    await session.refresh(membership)
    assert membership.tebex_subscription_id == sub_ref


@pytest.mark.asyncio
async def test_tebex_recurring_payment_status_changed_cancelled(client, session):
    """
    Tests recurring-payment.status.changed with status 5 (Cancelled) auditing cancellation.
    """
    sub_ref = "sub-status-cancel-99"

    payload = {
        "id": "evt-status-changed-1",
        "type": "recurring-payment.status.changed",
        "subject": {
            "reference": sub_ref,
            "status": {"id": 5, "description": "Cancelled"}
        }
    }

    resp = await client.post("/api/v1/webhooks/tebex", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"

    pr = (await session.exec(
        select(PaymentRecord).where(PaymentRecord.event_type == "recurring-payment.status.changed")
    )).first()
    assert pr is not None
    assert pr.status == "CANCELLED"


@pytest.mark.asyncio
async def test_tebex_refund_revokes_special_role(client, session):
    from src.connections.databases.db import Role, PlayerRole

    steam_id = "76561198000000999"
    tx_id = "tx-refund-special-role-1"

    player = Player(steam_id=steam_id, discord_id="discord-refunder")
    role = Role(code="VIP_FUNDADOR", name="VIP Fundador", role_type="SPECIAL", discord_role_id="999888111")
    session.add_all([player, role])
    await session.commit()
    await session.refresh(role)
    assert role.id is not None

    pr = PlayerRole(steam_id=steam_id, role_id=role.id)
    membership = Membership(
        steam_id=steam_id,
        membership_type="VIP_FUNDADOR",
        special_role_id=role.id,
        is_active=True,
        tebex_transaction_id=tx_id,
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc) + timedelta(days=30)
    )
    session.add_all([pr, membership])
    await session.commit()

    # Pre-condition: player has the special role
    active_pr = (await session.exec(select(PlayerRole).where(PlayerRole.steam_id == steam_id))).first()
    assert active_pr is not None

    # Refund webhook event
    payload = {
        "id": "evt-refund-1",
        "type": "payment.refunded",
        "subject": {
            "transaction_id": tx_id,
            "status": {"id": 3, "description": "Refunded"},
            "customer": {
                "username": {
                    "id": steam_id,
                    "username": "RefunderSteam"
                }
            }
        }
    }

    resp = await client.post("/api/v1/webhooks/tebex", json=payload)
    assert resp.status_code == 200

    # Membership deactivated
    await session.refresh(membership)
    assert membership.is_active is False

    # Special role revoked because of refund!
    revoked_pr = (await session.exec(select(PlayerRole).where(PlayerRole.steam_id == steam_id))).first()
    assert revoked_pr is None

