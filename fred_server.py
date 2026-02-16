"""Backward-compatible module entrypoint for the fred-mcp server.

The implementation now lives under the ``fred_mcp`` package.
"""

import asyncio

from fred_mcp.app import mcp
from fred_mcp.client import (
    BACKOFF_BASE_SECONDS,
    BACKOFF_MAX_SECONDS,
    FRED_API_BASE,
    FRED_V2_API_BASE,
    GEOFRED_API_BASE,
    HTTP_MAX_RETRIES,
    HTTP_TIMEOUT_SECONDS,
    RETRYABLE_STATUS_CODES,
    _fred_get,
    _fred_v2_get,
    _geofred_get,
)
from fred_mcp.errors import FredServerError
from fred_mcp.runtime import main
from fred_mcp.tools import *  # noqa: F401,F403

__all__ = [
    "asyncio",
    "mcp",
    "main",
    "FredServerError",
    "FRED_API_BASE",
    "GEOFRED_API_BASE",
    "FRED_V2_API_BASE",
    "HTTP_TIMEOUT_SECONDS",
    "HTTP_MAX_RETRIES",
    "BACKOFF_BASE_SECONDS",
    "BACKOFF_MAX_SECONDS",
    "RETRYABLE_STATUS_CODES",
    "_fred_get",
    "_geofred_get",
    "_fred_v2_get",
]


if __name__ == "__main__":
    main()
