import pytest

import fred_server


pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "tool",
    [fred_server.fred_request, fred_server.geofred_request, fred_server.fred_v2_request],
)
async def test_passthrough_invalid_json_returns_error_payload(tool) -> None:
    result = await tool(endpoint="series", params_json="{bad-json")

    assert set(result) == {"error", "error_details"}
    assert result["error"].startswith("Invalid JSON:")
    assert result["error_details"]["code"] == "validation_error"
    assert result["error_details"]["type"] == "validation_error"


@pytest.mark.parametrize(
    "tool",
    [fred_server.fred_request, fred_server.geofred_request, fred_server.fred_v2_request],
)
async def test_passthrough_non_object_json_returns_error_payload(tool) -> None:
    result = await tool(endpoint="series", params_json='["not", "an", "object"]')

    assert result["error"] == "JSON value must be an object"
    assert result["error_details"]["code"] == "validation_error"
    assert result["error_details"]["type"] == "validation_error"
