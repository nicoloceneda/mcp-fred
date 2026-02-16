import httpx
import pytest

import fred_server


pytestmark = pytest.mark.asyncio


async def test_get_releases_normalizes_invalid_enum_inputs(respx_mock) -> None:
    route = respx_mock.get(f"{fred_server.FRED_API_BASE}/releases").mock(
        return_value=httpx.Response(
            200,
            json={"count": 0, "offset": 0, "releases": []},
        )
    )

    await fred_server.get_releases(order_by="invalid-value", sort_order="UP")

    request = route.calls.last.request
    assert request.url.params["order_by"] == "release_id"
    assert request.url.params["sort_order"] == "desc"


async def test_get_releases_normalizes_case_insensitive_sort_order(respx_mock) -> None:
    route = respx_mock.get(f"{fred_server.FRED_API_BASE}/releases").mock(
        return_value=httpx.Response(
            200,
            json={"count": 0, "offset": 0, "releases": []},
        )
    )

    await fred_server.get_releases(sort_order=" AsC ")

    request = route.calls.last.request
    assert request.url.params["sort_order"] == "asc"


async def test_get_observations_returns_pagination_metadata(respx_mock) -> None:
    route = respx_mock.get(f"{fred_server.FRED_API_BASE}/series/observations").mock(
        return_value=httpx.Response(
            200,
            json={
                "count": 5000,
                "offset": 120,
                "observations": [
                    {"date": "2024-01-01", "value": "."},
                    {"date": "2024-02-01", "value": "1.23"},
                ],
            },
        )
    )

    result = await fred_server.get_observations(series_id="GDP", offset=20, limit=2)

    assert result["series_id"] == "GDP"
    assert result["count"] == 2
    assert result["offset"] == 120
    assert result["observations"] == [
        {"date": "2024-01-01", "value": None},
        {"date": "2024-02-01", "value": "1.23"},
    ]
    request = route.calls.last.request
    assert request.url.params["offset"] == "20"
    assert request.url.params["limit"] == "2"


@pytest.mark.parametrize("key_value", [None, "   "])
async def test_fred_get_requires_non_empty_api_key(
    monkeypatch: pytest.MonkeyPatch, key_value: str | None
) -> None:
    if key_value is None:
        monkeypatch.delenv("FRED_API_KEY", raising=False)
    else:
        monkeypatch.setenv("FRED_API_KEY", key_value)

    with pytest.raises(ValueError, match="Missing FRED_API_KEY environment variable"):
        await fred_server._fred_get("releases", {})


@pytest.mark.parametrize(
    ("getter", "base_url"),
    [
        (fred_server._fred_get, fred_server.FRED_API_BASE),
        (fred_server._geofred_get, fred_server.GEOFRED_API_BASE),
    ],
)
async def test_shared_v1_client_adds_query_api_key_and_file_type(
    getter, base_url: str, respx_mock
) -> None:
    endpoint = "mock/path"
    route = respx_mock.get(f"{base_url}/{endpoint}").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )

    result = await getter(endpoint, {"flag": True, "ignore": None})

    assert result == {"ok": True}
    request = route.calls.last.request
    assert request.url.params["api_key"] == "test-fred-api-key"
    assert request.url.params["file_type"] == "json"
    assert request.url.params["flag"] == "true"
    assert "ignore" not in request.url.params


async def test_v2_client_uses_api_key_header_not_query_param(respx_mock) -> None:
    endpoint = "release/observations"
    route = respx_mock.get(f"{fred_server.FRED_V2_API_BASE}/{endpoint}").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    await fred_server._fred_v2_get(endpoint, {"release_id": 10})

    request = route.calls.last.request
    assert request.headers["api_key"] == "test-fred-api-key"
    assert "api_key" not in request.url.params
    assert request.url.params["file_type"] == "json"


async def test_shared_http_client_retries_failed_requests(
    monkeypatch: pytest.MonkeyPatch, respx_mock
) -> None:
    endpoint = "retries"
    sleep_calls: list[float] = []

    async def _fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(fred_server.asyncio, "sleep", _fake_sleep)
    route = respx_mock.get(f"{fred_server.FRED_API_BASE}/{endpoint}").mock(
        side_effect=lambda request: httpx.Response(
            status_code=503,
            request=request,
            json={"error": "temporarily unavailable"},
        )
    )

    with pytest.raises(fred_server.FredServerError) as exc_info:
        await fred_server._fred_get(endpoint, {"key": "value"})

    payload = exc_info.value.payload
    assert payload["error_details"]["code"] == "upstream_http_error"
    assert payload["error_details"]["status_code"] == 503
    assert payload["error_details"]["retryable"] is True
    assert route.call_count == fred_server.HTTP_MAX_RETRIES + 1
    assert len(sleep_calls) == fred_server.HTTP_MAX_RETRIES
