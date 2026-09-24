import pytest
import aiohttp
import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

client_path = Path(__file__).resolve().parent.parent / "src" / "api_client.py"
spec = importlib.util.spec_from_file_location("discord_bot_api_client", client_path)
assert spec is not None and spec.loader is not None
client_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client_module)
APIClient = client_module.APIClient


@pytest.mark.asyncio
async def test_api_client_session_pooling():
    client = APIClient(base_url="http://127.0.0.1:8000", api_key="secret-key")
    assert client._session is None

    # First session creation
    session1 = await client._get_session()
    assert isinstance(session1, aiohttp.ClientSession)
    assert not session1.closed

    # Second call must reuse the exact same session (pooling)
    session2 = await client._get_session()
    assert session2 is session1

    # Clean close
    await client.close()
    assert session1.closed

    # Getting session again recreates a fresh session
    session3 = await client._get_session()
    assert session3 is not session1
    assert not session3.closed

    await client.close()


@pytest.mark.asyncio
async def test_api_client_headers():
    client = APIClient(base_url="http://api.matefield.com/", api_key="test-api-key")
    assert client.base_url == "http://api.matefield.com"
    assert client.headers["X-API-Key"] == "test-api-key"
    assert client.headers["Content-Type"] == "application/json"
    await client.close()


@pytest.mark.asyncio
async def test_api_client_request_delegation():
    client = APIClient(base_url="http://127.0.0.1:8000", api_key="secret-key")

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.json = AsyncMock(return_value={"ok": True, "total": 5})
    mock_response.raise_for_status = MagicMock()

    mock_request_ctx = AsyncMock()
    mock_request_ctx.__aenter__.return_value = mock_response

    with patch.object(aiohttp.ClientSession, "request", return_value=mock_request_ctx) as mock_req:
        result = await client._request("GET", "/api/v1/test")
        assert result == {"ok": True, "total": 5}
        mock_req.assert_called_once_with("GET", "http://127.0.0.1:8000/api/v1/test")

    await client.close()
