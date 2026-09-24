import json
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from src.connections.databases.db import get_session
from src.modules.v1.services.tebex_webhook_service import TebexWebhookService

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/tebex")
async def handle_tebex_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session)
):
    """
    Receives incoming webhook events from Tebex (validation, payment completed,
    recurring renewed, refunds, etc.).
    """
    raw_body = await request.body()
    sig_header = (
        request.headers.get("X-Signature")
        or request.headers.get("X-Tebex-Signature")
        or request.headers.get("X-BC-Signature")
    )

    # 1. Verify HMAC Signature
    if not TebexWebhookService.verify_signature(raw_body, sig_header):
        raise HTTPException(status_code=401, detail="Invalid X-Tebex-Signature")

    # 2. Parse JSON
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # 3. Process event
    raw_str = raw_body.decode("utf-8", errors="replace")
    return await TebexWebhookService.handle_webhook(payload, raw_str, session)
