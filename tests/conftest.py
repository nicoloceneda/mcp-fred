import pytest

import fred_server
from fred_mcp import client as fred_client


TEST_API_KEY = "test-fred-api-key"


@pytest.fixture(autouse=True)
def _set_default_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRED_API_KEY", TEST_API_KEY)


@pytest.fixture(autouse=True)
def _disable_live_network(respx_mock) -> None:
    # Prevent accidental real HTTP calls: unmatched requests fail the test.
    respx_mock.assert_all_mocked = True
    respx_mock.assert_all_called = False


@pytest.fixture(autouse=True)
async def _reset_shared_http_client() -> None:
    # Isolate tests from process-lifetime singleton state.
    if fred_client._http_client is not None:
        await fred_client._http_client.aclose()
    fred_client._http_client = None
    fred_client._http_client_lock = None
    yield
    if fred_client._http_client is not None:
        await fred_client._http_client.aclose()
    fred_client._http_client = None
    fred_client._http_client_lock = None
