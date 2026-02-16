import asyncio
import json
import logging
import os
import re
from typing import Any

import httpx
from dotenv import load_dotenv

from .errors import FredServerError, _error_payload

FRED_API_BASE = "https://api.stlouisfed.org/fred"
GEOFRED_API_BASE = "https://api.stlouisfed.org/geofred"
FRED_V2_API_BASE = "https://api.stlouisfed.org/fred/v2"

HTTP_TIMEOUT_SECONDS = 30.0
HTTP_MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 0.5
BACKOFF_MAX_SECONDS = 8.0
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

logger = logging.getLogger(__name__)

load_dotenv()

_http_client: httpx.AsyncClient | None = None
_http_client_lock: asyncio.Lock | None = None


def _redact_api_key_text(value: str) -> str:
    return re.sub(r"(api_key=)[^&\s]+", r"\1***", value)


def _sanitize_log_params(params: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in params.items():
        if key == "api_key":
            sanitized[key] = "***"
        else:
            sanitized[key] = value
    return sanitized


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


def _parse_json_object(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("JSON value must be an object")
    return parsed


async def _get_http_client() -> httpx.AsyncClient:
    global _http_client, _http_client_lock
    if _http_client is not None:
        return _http_client
    if _http_client_lock is None:
        _http_client_lock = asyncio.Lock()
    async with _http_client_lock:
        if _http_client is None:
            # Reuse one client so connections stay pooled across requests.
            _http_client = httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)
    return _http_client


def _retry_delay_seconds(
    attempt: int,
    response: httpx.Response | None = None,
) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                parsed_retry_after = float(retry_after)
                return max(0.0, min(parsed_retry_after, BACKOFF_MAX_SECONDS))
            except ValueError:
                pass
    return min(BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)), BACKOFF_MAX_SECONDS)


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
    normalized_endpoint = endpoint.strip("/")
    url = f"{base_url}/{normalized_endpoint}"
    safe_query = _sanitize_log_params(query)
    client = await _get_http_client()
    max_attempts = HTTP_MAX_RETRIES + 1

    # Retry transient upstream failures with exponential backoff.
    for attempt in range(1, max_attempts + 1):
        try:
            response = await client.get(url, params=query, headers=headers)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise FredServerError(
                    _error_payload(
                        "Upstream response was not a JSON object",
                        code="upstream_invalid_payload",
                        error_type="upstream_invalid_payload",
                        base_url=base_url,
                        endpoint=normalized_endpoint,
                        details={"attempt": attempt},
                    )
                )
            return payload
        except asyncio.CancelledError:
            raise
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            retryable = status_code in RETRYABLE_STATUS_CODES
            if retryable and attempt < max_attempts:
                delay = _retry_delay_seconds(attempt, exc.response)
                logger.warning(
                    "Retrying upstream HTTP error",
                    extra={
                        "base_url": base_url,
                        "endpoint": normalized_endpoint,
                        "status_code": status_code,
                        "attempt": attempt,
                        "delay_seconds": delay,
                        "query": safe_query,
                    },
                )
                await asyncio.sleep(delay)
                continue
            logger.error(
                "Upstream HTTP request failed",
                extra={
                    "base_url": base_url,
                    "endpoint": normalized_endpoint,
                    "status_code": status_code,
                    "retryable": retryable,
                    "attempt": attempt,
                    "query": safe_query,
                },
            )
            raise FredServerError(
                _error_payload(
                    f"Upstream request failed with status {status_code}",
                    code="upstream_http_error",
                    error_type="upstream_http_error",
                    base_url=base_url,
                    endpoint=normalized_endpoint,
                    status_code=status_code,
                    retryable=retryable,
                    details={"attempt": attempt},
                )
            ) from exc
        except httpx.RequestError as exc:
            redacted_reason = _redact_api_key_text(str(exc))
            if attempt < max_attempts:
                delay = _retry_delay_seconds(attempt)
                logger.warning(
                    "Retrying upstream network error",
                    extra={
                        "base_url": base_url,
                        "endpoint": normalized_endpoint,
                        "attempt": attempt,
                        "delay_seconds": delay,
                        "query": safe_query,
                        "reason": redacted_reason,
                    },
                )
                await asyncio.sleep(delay)
                continue
            logger.error(
                "Upstream network request failed",
                extra={
                    "base_url": base_url,
                    "endpoint": normalized_endpoint,
                    "attempt": attempt,
                    "query": safe_query,
                    "reason": redacted_reason,
                },
            )
            raise FredServerError(
                _error_payload(
                    "Network error while contacting upstream API",
                    code="upstream_network_error",
                    error_type="upstream_network_error",
                    base_url=base_url,
                    endpoint=normalized_endpoint,
                    retryable=True,
                    details={"attempt": attempt},
                )
            ) from exc
        except ValueError as exc:
            logger.error(
                "Upstream response JSON decode failed",
                extra={
                    "base_url": base_url,
                    "endpoint": normalized_endpoint,
                    "attempt": attempt,
                    "query": safe_query,
                },
            )
            raise FredServerError(
                _error_payload(
                    "Failed to decode upstream JSON response",
                    code="upstream_invalid_json",
                    error_type="upstream_invalid_json",
                    base_url=base_url,
                    endpoint=normalized_endpoint,
                    details={"attempt": attempt, "reason": str(exc)},
                )
            ) from exc


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
