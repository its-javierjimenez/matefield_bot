import pytest
from unittest.mock import MagicMock
from src.plugins.database import build_player_memberships_view
from src.api_client import APIClient


def test_build_player_memberships_view_all_fields():
    app_mock = MagicMock()
    app_mock.rest.build_message_action_row.return_value = MagicMock()

    memberships_data = [
        {
            "id": 42,
            "steam_id": "76561198000000001",
            "type": "VIP_COMUN",
            "is_active": True,
            "start_date": "2026-09-01T12:00:00+00:00",
            "end_date": "2026-10-01T12:00:00+00:00",
            "special_role": "ADMIN",
            "special_role_id": 999999,
            "rcon_sync_status": "SUCCESS"
        }
    ]

    embed, components = build_player_memberships_view(
        app_mock,
        usuario_id=123456789,
        memberships=memberships_data,
        page=1,
        total=1,
        limit=5
    )

    assert embed.title is not None and "Historial de Membresías" in embed.title
    assert len(embed.fields) == 1
    field = embed.fields[0]

    # Verify that all table fields are rendered in the field
    assert "Membresía #42" in field.name
    assert "VIP_COMUN" in field.name
    assert "🟢 Activa" in field.value
    assert "is_active=True" in field.value
    assert "76561198000000001" in field.value
    assert "2026-09-01 12:00:00" in field.value
    assert "2026-10-01 12:00:00" in field.value
    assert "999999" in field.value
    assert "SUCCESS" in field.value


@pytest.mark.asyncio
async def test_api_client_get_paginated_memberships_url(monkeypatch):
    client = APIClient("http://test-server", "secret-key")

    requested_url: str | None = None

    async def mock_request(method, endpoint, **kwargs):
        nonlocal requested_url
        requested_url = endpoint
        return {"page": 1, "limit": 5, "total": 0, "memberships": []}

    monkeypatch.setattr(client, "_request", mock_request)

    res = await client.get_paginated_memberships(page=2, limit=5, discord_id="123456")
    assert requested_url is not None and "/api/v1/db/memberships?page=2&limit=5&discord_id=123456" in requested_url
    assert res["memberships"] == []


@pytest.mark.asyncio
async def test_api_client_export_memberships(monkeypatch):
    client = APIClient("http://test-server", "secret-key")

    requested_method: str | None = None
    requested_url: str | None = None

    async def mock_request(method, endpoint, **kwargs):
        nonlocal requested_method, requested_url
        requested_method = method
        requested_url = endpoint
        return {
            "ok": True,
            "filename": "memberships_export_test.csv",
            "download_url": "http://test-server/download",
            "total_records": 10,
            "size_bytes": 1024,
            "expires_in_seconds": 1800
        }

    monkeypatch.setattr(client, "_request", mock_request)

    res = await client.export_memberships()
    assert requested_method == "POST"
    assert requested_url == "/api/v1/db/memberships/export"
    assert res["ok"] is True
    assert res["filename"] == "memberships_export_test.csv"

