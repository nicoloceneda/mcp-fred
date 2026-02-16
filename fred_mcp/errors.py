import asyncio
import logging
from functools import wraps
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


class FredServerError(Exception):
    def __init__(self, payload: dict[str, Any]):
        super().__init__(payload.get("error", "FRED server error"))
        self.payload = payload


def _error_payload(
    message: str,
    *,
    code: str,
    error_type: str,
    base_url: str | None = None,
    endpoint: str | None = None,
    status_code: int | None = None,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # Keep top-level "error" for backwards compatibility with existing clients.
    return {
        "error": message,
        "error_details": {
            "type": error_type,
            "code": code,
            "base_url": base_url,
            "endpoint": endpoint.strip("/") if endpoint else None,
            "status_code": status_code,
            "retryable": retryable,
            "details": details or {},
        },
    }


def _tool_error_boundary(
    func: Callable[..., Awaitable[dict[str, Any]]],
) -> Callable[..., Awaitable[dict[str, Any]]]:
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            return await func(*args, **kwargs)
        except asyncio.CancelledError:
            raise
        except FredServerError as exc:
            return exc.payload
        except ValueError as exc:
            return _error_payload(
                str(exc),
                code="validation_error",
                error_type="validation_error",
            )
        except Exception as exc:
            logger.exception("Unhandled tool error in '%s'", func.__name__)
            return _error_payload(
                "Internal server error",
                code="internal_error",
                error_type="internal_error",
                details={"exception_type": type(exc).__name__},
            )

    return wrapper
