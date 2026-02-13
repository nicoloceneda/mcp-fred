import json
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

FRED_API_BASE = "https://api.stlouisfed.org/fred"
GEOFRED_API_BASE = "https://api.stlouisfed.org/geofred"
FRED_V2_API_BASE = "https://api.stlouisfed.org/fred/v2"

load_dotenv()

mcp = FastMCP(
    "fred-mcp",
    instructions=(
        "Query FRED API v1, GeoFRED maps API, and FRED API v2 release observations."
    ),
)


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(value, high))


def _non_negative(value: int) -> int:
    return max(0, value)


def _normalize_sort_order(value: str) -> str:
    return "asc" if value.strip().lower() == "asc" else "desc"


def _normalize_release_order_by(value: str) -> str:
    valid = {"release_id", "name", "press_release", "realtime_start", "realtime_end"}
    candidate = value.strip().lower()
    return candidate if candidate in valid else "release_id"


def _fred_api_key() -> str:
    key = os.getenv("FRED_API_KEY", "").strip()
    if not key:
        raise ValueError("Missing FRED_API_KEY environment variable")
    return key


def _clean_params(params: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            cleaned[key] = str(value).lower()
        else:
            cleaned[key] = value
    return cleaned


def _compact_series_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "title": row.get("title"),
        "frequency": row.get("frequency"),
        "units": row.get("units"),
        "observation_start": row.get("observation_start"),
        "observation_end": row.get("observation_end"),
        "popularity": row.get("popularity"),
    }


def _parse_json_object(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("JSON value must be an object")
    return parsed


async def _http_get_json(
    base_url: str,
    endpoint: str,
    params: dict[str, Any],
    headers: dict[str, str] | None = None,
    include_api_key_query: bool = True,
) -> dict[str, Any]:
    query = _clean_params(params)
    if include_api_key_query:
        query["api_key"] = _fred_api_key()
    query["file_type"] = "json"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{base_url}/{endpoint.strip('/')}", params=query, headers=headers
        )
        response.raise_for_status()
        return response.json()


async def _fred_get(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    return await _http_get_json(FRED_API_BASE, endpoint, params)


async def _geofred_get(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    return await _http_get_json(GEOFRED_API_BASE, endpoint, params)


async def _fred_v2_get(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    return await _http_get_json(
        FRED_V2_API_BASE,
        endpoint,
        params,
        headers={"api_key": _fred_api_key()},
        include_api_key_query=False,
    )


# ----------------------------
# Generic passthrough tools
# ----------------------------

@mcp.tool()
async def fred_request(endpoint: str, params_json: str = "{}") -> dict[str, Any]:
    """Call any FRED API v1 endpoint path directly."""
    try:
        params = _parse_json_object(params_json)
    except ValueError as exc:
        return {"error": str(exc)}
    return await _fred_get(endpoint, params)


@mcp.tool()
async def geofred_request(endpoint: str, params_json: str = "{}") -> dict[str, Any]:
    """Call any GeoFRED API endpoint path directly."""
    try:
        params = _parse_json_object(params_json)
    except ValueError as exc:
        return {"error": str(exc)}
    return await _geofred_get(endpoint, params)


@mcp.tool()
async def fred_v2_request(endpoint: str, params_json: str = "{}") -> dict[str, Any]:
    """Call any FRED API v2 endpoint path directly."""
    try:
        params = _parse_json_object(params_json)
    except ValueError as exc:
        return {"error": str(exc)}
    return await _fred_v2_get(endpoint, params)


# ----------------------------
# Categories endpoints (v1)
# ----------------------------

@mcp.tool()
async def get_category(
    category_id: int = 0,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
) -> dict[str, Any]:
    """fred/category"""
    data = await _fred_get(
        "category",
        {
            "category_id": category_id,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
        },
    )
    categories = data.get("categories", [])
    if not categories:
        return {"error": f"Category '{category_id}' not found"}
    return categories[0]


@mcp.tool()
async def get_category_children(
    category_id: int = 0,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
) -> dict[str, Any]:
    """fred/category/children"""
    return await _fred_get(
        "category/children",
        {
            "category_id": category_id,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
        },
    )


@mcp.tool()
async def get_category_related(
    category_id: int,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
) -> dict[str, Any]:
    """fred/category/related"""
    return await _fred_get(
        "category/related",
        {
            "category_id": category_id,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
        },
    )


@mcp.tool()
async def get_category_series(
    category_id: int,
    limit: int = 20,
    offset: int = 0,
    order_by: str = "popularity",
    sort_order: str = "desc",
    filter_variable: str | None = None,
    filter_value: str | None = None,
    tag_names: str | None = None,
    exclude_tag_names: str | None = None,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
) -> dict[str, Any]:
    """fred/category/series"""
    data = await _fred_get(
        "category/series",
        {
            "category_id": category_id,
            "limit": _clamp(limit, 1, 1000),
            "offset": _non_negative(offset),
            "order_by": order_by,
            "sort_order": _normalize_sort_order(sort_order),
            "filter_variable": filter_variable,
            "filter_value": filter_value,
            "tag_names": tag_names,
            "exclude_tag_names": exclude_tag_names,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
        },
    )
    series_rows = [_compact_series_row(row) for row in data.get("seriess", [])]
    return {
        "category_id": category_id,
        "count": data.get("count", len(series_rows)),
        "offset": data.get("offset", offset),
        "results": series_rows,
    }


@mcp.tool()
async def get_category_tags(
    category_id: int,
    limit: int = 20,
    offset: int = 0,
    order_by: str = "series_count",
    sort_order: str = "desc",
    tag_names: str | None = None,
    tag_group_id: str | None = None,
    search_text: str | None = None,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
) -> dict[str, Any]:
    """fred/category/tags"""
    return await _fred_get(
        "category/tags",
        {
            "category_id": category_id,
            "limit": _clamp(limit, 1, 1000),
            "offset": _non_negative(offset),
            "order_by": order_by,
            "sort_order": _normalize_sort_order(sort_order),
            "tag_names": tag_names,
            "tag_group_id": tag_group_id,
            "search_text": search_text,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
        },
    )


@mcp.tool()
async def get_category_related_tags(
    category_id: int,
    tag_names: str,
    exclude_tag_names: str | None = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str = "series_count",
    sort_order: str = "desc",
    tag_group_id: str | None = None,
    search_text: str | None = None,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
) -> dict[str, Any]:
    """fred/category/related_tags"""
    return await _fred_get(
        "category/related_tags",
        {
            "category_id": category_id,
            "tag_names": tag_names,
            "exclude_tag_names": exclude_tag_names,
            "limit": _clamp(limit, 1, 1000),
            "offset": _non_negative(offset),
            "order_by": order_by,
            "sort_order": _normalize_sort_order(sort_order),
            "tag_group_id": tag_group_id,
            "search_text": search_text,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
        },
    )


# ----------------------------
# Releases endpoints (v1)
# ----------------------------

@mcp.tool()
async def get_releases(
    limit: int = 20,
    offset: int = 0,
    order_by: str = "release_id",
    sort_order: str = "desc",
    realtime_start: str | None = None,
    realtime_end: str | None = None,
) -> dict[str, Any]:
    """fred/releases"""
    data = await _fred_get(
        "releases",
        {
            "limit": _clamp(limit, 1, 1000),
            "offset": _non_negative(offset),
            "order_by": _normalize_release_order_by(order_by),
            "sort_order": _normalize_sort_order(sort_order),
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
        },
    )
    releases = [
        {
            "id": release.get("id"),
            "name": release.get("name"),
            "press_release": release.get("press_release"),
            "link": release.get("link"),
        }
        for release in data.get("releases", [])
    ]
    return {
        "count": data.get("count", len(releases)),
        "offset": data.get("offset", offset),
        "releases": releases,
    }


@mcp.tool()
async def get_releases_dates(
    limit: int = 20,
    offset: int = 0,
    sort_order: str = "desc",
    include_release_dates_with_no_data: bool = False,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
) -> dict[str, Any]:
    """fred/releases/dates"""
    return await _fred_get(
        "releases/dates",
        {
            "limit": _clamp(limit, 1, 1000),
            "offset": _non_negative(offset),
            "sort_order": _normalize_sort_order(sort_order),
            "include_release_dates_with_no_data": include_release_dates_with_no_data,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
        },
    )


@mcp.tool()
async def get_release(
    release_id: int,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
) -> dict[str, Any]:
    """fred/release"""
    return await _fred_get(
        "release",
        {
            "release_id": release_id,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
        },
    )


@mcp.tool()
async def get_release_dates(
    release_id: int,
    limit: int = 20,
    offset: int = 0,
    sort_order: str = "desc",
    include_release_dates_with_no_data: bool = False,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
) -> dict[str, Any]:
    """fred/release/dates"""
    return await _fred_get(
        "release/dates",
        {
            "release_id": release_id,
            "limit": _clamp(limit, 1, 10000),
            "offset": _non_negative(offset),
            "sort_order": _normalize_sort_order(sort_order),
            "include_release_dates_with_no_data": include_release_dates_with_no_data,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
        },
    )


@mcp.tool()
async def get_release_series(
    release_id: int,
    limit: int = 20,
    offset: int = 0,
    order_by: str = "popularity",
    sort_order: str = "desc",
    filter_variable: str | None = None,
    filter_value: str | None = None,
    tag_names: str | None = None,
    exclude_tag_names: str | None = None,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
) -> dict[str, Any]:
    """fred/release/series"""
    data = await _fred_get(
        "release/series",
        {
            "release_id": release_id,
            "limit": _clamp(limit, 1, 1000),
            "offset": _non_negative(offset),
            "order_by": order_by,
            "sort_order": _normalize_sort_order(sort_order),
            "filter_variable": filter_variable,
            "filter_value": filter_value,
            "tag_names": tag_names,
            "exclude_tag_names": exclude_tag_names,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
        },
    )
    series_rows = [_compact_series_row(row) for row in data.get("seriess", [])]
    return {
        "release_id": release_id,
        "count": data.get("count", len(series_rows)),
        "offset": data.get("offset", offset),
        "results": series_rows,
    }


@mcp.tool()
async def get_release_sources(
    release_id: int,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
) -> dict[str, Any]:
    """fred/release/sources"""
    return await _fred_get(
        "release/sources",
        {
            "release_id": release_id,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
        },
    )


@mcp.tool()
async def get_release_tags(
    release_id: int,
    limit: int = 20,
    offset: int = 0,
    order_by: str = "series_count",
    sort_order: str = "desc",
    tag_names: str | None = None,
    tag_group_id: str | None = None,
    search_text: str | None = None,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
) -> dict[str, Any]:
    """fred/release/tags"""
    return await _fred_get(
        "release/tags",
        {
            "release_id": release_id,
            "limit": _clamp(limit, 1, 1000),
            "offset": _non_negative(offset),
            "order_by": order_by,
            "sort_order": _normalize_sort_order(sort_order),
            "tag_names": tag_names,
            "tag_group_id": tag_group_id,
            "search_text": search_text,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
        },
    )


@mcp.tool()
async def get_release_related_tags(
    release_id: int,
    tag_names: str,
    exclude_tag_names: str | None = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str = "series_count",
    sort_order: str = "desc",
    tag_group_id: str | None = None,
    search_text: str | None = None,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
) -> dict[str, Any]:
    """fred/release/related_tags"""
    return await _fred_get(
        "release/related_tags",
        {
            "release_id": release_id,
            "tag_names": tag_names,
            "exclude_tag_names": exclude_tag_names,
            "limit": _clamp(limit, 1, 1000),
            "offset": _non_negative(offset),
            "order_by": order_by,
            "sort_order": _normalize_sort_order(sort_order),
            "tag_group_id": tag_group_id,
            "search_text": search_text,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
        },
    )


@mcp.tool()
async def get_release_tables(
    release_id: int,
    element_id: int | None = None,
    observation_date: str | None = None,
    include_observation_values: bool = False,
) -> dict[str, Any]:
    """fred/release/tables"""
    return await _fred_get(
        "release/tables",
        {
            "release_id": release_id,
            "element_id": element_id,
            "observation_date": observation_date,
            "include_observation_values": include_observation_values,
        },
    )


# ----------------------------
# Series endpoints (v1)
# ----------------------------

@mcp.tool()
async def get_series(
    series_id: str,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
) -> dict[str, Any]:
    """fred/series"""
    data = await _fred_get(
        "series",
        {
            "series_id": series_id,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
        },
    )
    rows = data.get("seriess", [])
    if not rows:
        return {"error": f"Series '{series_id}' not found"}
    return rows[0]


@mcp.tool()
async def get_series_categories(
    series_id: str,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
) -> dict[str, Any]:
    """fred/series/categories"""
    return await _fred_get(
        "series/categories",
        {
            "series_id": series_id,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
        },
    )


@mcp.tool()
async def get_observations(
    series_id: str,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
    limit: int = 100,
    offset: int = 0,
    sort_order: str = "desc",
    observation_start: str | None = None,
    observation_end: str | None = None,
    units: str | None = None,
    frequency: str | None = None,
    aggregation_method: str | None = None,
    output_type: int | None = None,
    vintage_dates: str | None = None,
) -> dict[str, Any]:
    """fred/series/observations"""
    data = await _fred_get(
        "series/observations",
        {
            "series_id": series_id,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
            "limit": _clamp(limit, 1, 100000),
            "offset": _non_negative(offset),
            "sort_order": _normalize_sort_order(sort_order),
            "observation_start": observation_start,
            "observation_end": observation_end,
            "units": units,
            "frequency": frequency,
            "aggregation_method": aggregation_method,
            "output_type": output_type,
            "vintage_dates": vintage_dates,
        },
    )
    observations = data.get("observations", [])
    cleaned = [
        {"date": row.get("date"), "value": None if row.get("value") == "." else row.get("value")}
        for row in observations
    ]
    return {
        "series_id": series_id,
        "count": len(cleaned),
        "offset": data.get("offset", offset),
        "observations": cleaned,
    }


@mcp.tool()
async def get_series_observations(
    series_id: str,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
    limit: int = 100,
    offset: int = 0,
    sort_order: str = "desc",
    observation_start: str | None = None,
    observation_end: str | None = None,
    units: str | None = None,
    frequency: str | None = None,
    aggregation_method: str | None = None,
    output_type: int | None = None,
    vintage_dates: str | None = None,
) -> dict[str, Any]:
    """Alias for get_observations."""
    return await get_observations(
        series_id=series_id,
        realtime_start=realtime_start,
        realtime_end=realtime_end,
        limit=limit,
        offset=offset,
        sort_order=sort_order,
        observation_start=observation_start,
        observation_end=observation_end,
        units=units,
        frequency=frequency,
        aggregation_method=aggregation_method,
        output_type=output_type,
        vintage_dates=vintage_dates,
    )


@mcp.tool()
async def get_series_release(
    series_id: str,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
) -> dict[str, Any]:
    """fred/series/release"""
    return await _fred_get(
        "series/release",
        {
            "series_id": series_id,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
        },
    )


@mcp.tool()
async def search_series(
    query: str,
    search_type: str | None = None,
    limit: int = 10,
    offset: int = 0,
    order_by: str = "search_rank",
    sort_order: str = "desc",
    filter_variable: str | None = None,
    filter_value: str | None = None,
    tag_names: str | None = None,
    exclude_tag_names: str | None = None,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
) -> dict[str, Any]:
    """fred/series/search"""
    data = await _fred_get(
        "series/search",
        {
            "search_text": query,
            "search_type": search_type,
            "limit": _clamp(limit, 1, 1000),
            "offset": _non_negative(offset),
            "order_by": order_by,
            "sort_order": _normalize_sort_order(sort_order),
            "filter_variable": filter_variable,
            "filter_value": filter_value,
            "tag_names": tag_names,
            "exclude_tag_names": exclude_tag_names,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
        },
    )
    series_rows = [_compact_series_row(row) for row in data.get("seriess", [])]
    return {
        "count": data.get("count", len(series_rows)),
        "offset": data.get("offset", offset),
        "results": series_rows,
    }


@mcp.tool()
async def search_series_by_tags(
    series_search_text: str,
    tag_names: str | None = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str = "series_count",
    sort_order: str = "desc",
    tag_group_id: str | None = None,
    search_text: str | None = None,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
) -> dict[str, Any]:
    """fred/series/search/tags"""
    return await _fred_get(
        "series/search/tags",
        {
            "series_search_text": series_search_text,
            "tag_names": tag_names,
            "limit": _clamp(limit, 1, 1000),
            "offset": _non_negative(offset),
            "order_by": order_by,
            "sort_order": _normalize_sort_order(sort_order),
            "tag_group_id": tag_group_id,
            "search_text": search_text,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
        },
    )


@mcp.tool()
async def search_series_related_tags(
    series_search_text: str,
    tag_names: str,
    exclude_tag_names: str | None = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str = "series_count",
    sort_order: str = "desc",
    tag_group_id: str | None = None,
    search_text: str | None = None,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
) -> dict[str, Any]:
    """fred/series/search/related_tags"""
    return await _fred_get(
        "series/search/related_tags",
        {
            "series_search_text": series_search_text,
            "tag_names": tag_names,
            "exclude_tag_names": exclude_tag_names,
            "limit": _clamp(limit, 1, 1000),
            "offset": _non_negative(offset),
            "order_by": order_by,
            "sort_order": _normalize_sort_order(sort_order),
            "tag_group_id": tag_group_id,
            "search_text": search_text,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
        },
    )


@mcp.tool()
async def get_series_tags(
    series_id: str,
    limit: int = 20,
    offset: int = 0,
    order_by: str = "series_count",
    sort_order: str = "desc",
    tag_names: str | None = None,
    tag_group_id: str | None = None,
    search_text: str | None = None,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
) -> dict[str, Any]:
    """fred/series/tags"""
    return await _fred_get(
        "series/tags",
        {
            "series_id": series_id,
            "limit": _clamp(limit, 1, 1000),
            "offset": _non_negative(offset),
            "order_by": order_by,
            "sort_order": _normalize_sort_order(sort_order),
            "tag_names": tag_names,
            "tag_group_id": tag_group_id,
            "search_text": search_text,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
        },
    )


@mcp.tool()
async def get_series_updates(
    realtime_start: str | None = None,
    realtime_end: str | None = None,
    limit: int = 20,
    offset: int = 0,
    filter_value: str = "all",
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict[str, Any]:
    """fred/series/updates"""
    return await _fred_get(
        "series/updates",
        {
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
            "limit": _clamp(limit, 1, 1000),
            "offset": _non_negative(offset),
            "filter_value": filter_value,
            "start_time": start_time,
            "end_time": end_time,
        },
    )


@mcp.tool()
async def get_series_vintage_dates(
    series_id: str,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
    limit: int = 100,
    offset: int = 0,
    sort_order: str = "desc",
) -> dict[str, Any]:
    """fred/series/vintagedates"""
    return await _fred_get(
        "series/vintagedates",
        {
            "series_id": series_id,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
            "limit": _clamp(limit, 1, 10000),
            "offset": _non_negative(offset),
            "sort_order": _normalize_sort_order(sort_order),
        },
    )


# ----------------------------
# Sources endpoints (v1)
# ----------------------------

@mcp.tool()
async def get_sources(
    realtime_start: str | None = None,
    realtime_end: str | None = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str = "source_id",
    sort_order: str = "asc",
) -> dict[str, Any]:
    """fred/sources"""
    return await _fred_get(
        "sources",
        {
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
            "limit": _clamp(limit, 1, 1000),
            "offset": _non_negative(offset),
            "order_by": order_by,
            "sort_order": _normalize_sort_order(sort_order),
        },
    )


@mcp.tool()
async def get_source(
    source_id: int,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
) -> dict[str, Any]:
    """fred/source"""
    return await _fred_get(
        "source",
        {
            "source_id": source_id,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
        },
    )


@mcp.tool()
async def get_source_releases(
    source_id: int,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str = "release_id",
    sort_order: str = "asc",
) -> dict[str, Any]:
    """fred/source/releases"""
    return await _fred_get(
        "source/releases",
        {
            "source_id": source_id,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
            "limit": _clamp(limit, 1, 1000),
            "offset": _non_negative(offset),
            "order_by": order_by,
            "sort_order": _normalize_sort_order(sort_order),
        },
    )


# ----------------------------
# Tags endpoints (v1)
# ----------------------------

@mcp.tool()
async def get_tags(
    realtime_start: str | None = None,
    realtime_end: str | None = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str = "series_count",
    sort_order: str = "desc",
    tag_names: str | None = None,
    tag_group_id: str | None = None,
    search_text: str | None = None,
) -> dict[str, Any]:
    """fred/tags"""
    return await _fred_get(
        "tags",
        {
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
            "limit": _clamp(limit, 1, 1000),
            "offset": _non_negative(offset),
            "order_by": order_by,
            "sort_order": _normalize_sort_order(sort_order),
            "tag_names": tag_names,
            "tag_group_id": tag_group_id,
            "search_text": search_text,
        },
    )


@mcp.tool()
async def get_related_tags(
    tag_names: str,
    exclude_tag_names: str | None = None,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str = "series_count",
    sort_order: str = "desc",
    tag_group_id: str | None = None,
    search_text: str | None = None,
) -> dict[str, Any]:
    """fred/related_tags"""
    return await _fred_get(
        "related_tags",
        {
            "tag_names": tag_names,
            "exclude_tag_names": exclude_tag_names,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
            "limit": _clamp(limit, 1, 1000),
            "offset": _non_negative(offset),
            "order_by": order_by,
            "sort_order": _normalize_sort_order(sort_order),
            "tag_group_id": tag_group_id,
            "search_text": search_text,
        },
    )


@mcp.tool()
async def get_tag_series(
    tag_names: str,
    exclude_tag_names: str | None = None,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str = "popularity",
    sort_order: str = "desc",
) -> dict[str, Any]:
    """fred/tags/series"""
    data = await _fred_get(
        "tags/series",
        {
            "tag_names": tag_names,
            "exclude_tag_names": exclude_tag_names,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
            "limit": _clamp(limit, 1, 1000),
            "offset": _non_negative(offset),
            "order_by": order_by,
            "sort_order": _normalize_sort_order(sort_order),
        },
    )
    series_rows = [_compact_series_row(row) for row in data.get("seriess", [])]
    return {
        "count": data.get("count", len(series_rows)),
        "offset": data.get("offset", offset),
        "results": series_rows,
    }


# ----------------------------
# GeoFRED maps endpoints
# ----------------------------

@mcp.tool()
async def get_map_shape_file(shape: str) -> dict[str, Any]:
    """geofred/shapes/file"""
    return await _geofred_get("shapes/file", {"shape": shape})


@mcp.tool()
async def get_map_series_group(series_id: str) -> dict[str, Any]:
    """geofred/series/group"""
    return await _geofred_get("series/group", {"series_id": series_id})


@mcp.tool()
async def get_map_series_data(
    series_id: str,
    date: str | None = None,
    start_date: str | None = None,
) -> dict[str, Any]:
    """geofred/series/data"""
    return await _geofred_get(
        "series/data",
        {"series_id": series_id, "date": date, "start_date": start_date},
    )


@mcp.tool()
async def get_map_regional_data(
    series_group: str,
    region_type: str,
    date: str,
    start_date: str | None = None,
    season: str | None = None,
    units: str | None = None,
    transformation: str | None = None,
    frequency: str | None = None,
    aggregation_method: str | None = None,
) -> dict[str, Any]:
    """geofred/regional/data"""
    return await _geofred_get(
        "regional/data",
        {
            "series_group": series_group,
            "region_type": region_type,
            "date": date,
            "start_date": start_date,
            "season": season,
            "units": units,
            "transformation": transformation,
            "frequency": frequency,
            "aggregation_method": aggregation_method,
        },
    )


# ----------------------------
# FRED v2 endpoints
# ----------------------------

@mcp.tool()
async def get_release_observations_v2(
    release_id: int,
    date: str | None = None,
    series_id: str | None = None,
    limit: int = 1000,
    offset: int = 0,
    sort_order: str = "desc",
    next_cursor: str | None = None,
) -> dict[str, Any]:
    """fred/v2/release/observations"""
    return await _fred_v2_get(
        "release/observations",
        {
            "release_id": release_id,
            "date": date,
            "series_id": series_id,
            "limit": _clamp(limit, 1, 500000),
            "offset": _non_negative(offset),
            "sort_order": _normalize_sort_order(sort_order),
            "next_cursor": next_cursor,
        },
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
