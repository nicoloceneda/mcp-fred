from typing import Any

RELEASE_ORDER_BY_VALUES = {
    "release_id",
    "name",
    "press_release",
    "realtime_start",
    "realtime_end",
}
SERIES_ORDER_BY_VALUES = {
    "series_id",
    "title",
    "units",
    "frequency",
    "seasonal_adjustment",
    "realtime_start",
    "realtime_end",
    "last_updated",
    "observation_start",
    "observation_end",
    "popularity",
    "group_popularity",
}
SEARCH_SERIES_ORDER_BY_VALUES = SERIES_ORDER_BY_VALUES | {"search_rank"}
TAGS_ORDER_BY_VALUES = {"series_count", "popularity", "created", "name", "group_id"}
SOURCES_ORDER_BY_VALUES = {"source_id", "name", "realtime_start", "realtime_end"}

ORDER_BY_RULES: dict[str, tuple[str, set[str]]] = {
    "category/series": ("popularity", SERIES_ORDER_BY_VALUES),
    "category/tags": ("series_count", TAGS_ORDER_BY_VALUES),
    "category/related_tags": ("series_count", TAGS_ORDER_BY_VALUES),
    "releases": ("release_id", RELEASE_ORDER_BY_VALUES),
    "release/series": ("popularity", SERIES_ORDER_BY_VALUES),
    "release/tags": ("series_count", TAGS_ORDER_BY_VALUES),
    "release/related_tags": ("series_count", TAGS_ORDER_BY_VALUES),
    "series/search": ("search_rank", SEARCH_SERIES_ORDER_BY_VALUES),
    "series/search/tags": ("series_count", TAGS_ORDER_BY_VALUES),
    "series/search/related_tags": ("series_count", TAGS_ORDER_BY_VALUES),
    "series/tags": ("series_count", TAGS_ORDER_BY_VALUES),
    "sources": ("source_id", SOURCES_ORDER_BY_VALUES),
    "source/releases": ("release_id", RELEASE_ORDER_BY_VALUES),
    "tags": ("series_count", TAGS_ORDER_BY_VALUES),
    "related_tags": ("series_count", TAGS_ORDER_BY_VALUES),
    "tags/series": ("popularity", SERIES_ORDER_BY_VALUES),
}


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(value, high))


def _non_negative(value: int) -> int:
    return max(0, value)


def _normalize_limit(value: int, low: int, high: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = low
    return _clamp(parsed, low, high)


def _normalize_offset(value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 0
    return _non_negative(parsed)


def _normalize_enum(value: Any, valid: set[str], default: str) -> str:
    candidate = str(value).strip().lower() if value is not None else ""
    return candidate if candidate in valid else default


def _normalize_sort_order(value: str) -> str:
    return _normalize_enum(value, {"asc", "desc"}, "desc")


def _normalize_order_by(endpoint: str, value: str) -> str:
    if endpoint not in ORDER_BY_RULES:
        raise ValueError(f"Unsupported order_by endpoint '{endpoint}'")
    default, valid = ORDER_BY_RULES[endpoint]
    return _normalize_enum(value, valid, default)
