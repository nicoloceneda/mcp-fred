from .app import mcp
from . import tools as _tools  # noqa: F401


def main() -> None:
    mcp.run(transport="stdio")
