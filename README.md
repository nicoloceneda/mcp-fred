# Fred St Louis MCP

![Project cover](assets/project_cover.png)

![Status: Active Development and Maintained](https://img.shields.io/badge/status-active%20development%20%26%20maintained-brightgreen)

*Author*: Nicolo Ceneda \
*Contact*: n.ceneda20@imperial.ac.uk \
*Website*: [nicoloceneda.github.io](https://nicoloceneda.github.io/) \
*Institution*: Imperial College London \
*Course*: PhD in Finance

## Description

MCP server for:
- FRED API v1 (`/fred/*`)
- GeoFRED maps API (`/geofred/*`)
- FRED API v2 (`/fred/v2/*`, including a dedicated tool for `release/observations`)

## Requirements

- Python `>=3.11`
- A FRED API key from [FRED API Keys](https://fred.stlouisfed.org/docs/api/api_key.html)

## Install

First, `cd` into the directory where you want the `mcp-fred` repository to be created. Then execute the following commands from the terminal.

```bash
git clone https://github.com/nicoloceneda/mcp-fred.git
cd mcp-fred
python3 -m venv .venv
.venv/bin/pip install -e .
```

## API key setup

Create a local `.env`:

```bash
cp .env.example .env
```

Then set:

```dotenv
FRED_API_KEY=your_fred_api_key_here
```

## Configure MCP clients

### Codex CLI/Desktop

Add once:

```bash
codex mcp add fred -- /absolute/path/to/fred-mcp/.venv/bin/python /absolute/path/to/fred-mcp/fred_server.py
```

Check:

```bash
codex mcp list
codex mcp get fred
```

### Generic `mcpServers` JSON config

```json
{
  "mcpServers": {
    "fred": {
      "command": "/absolute/path/to/fred-mcp/.venv/bin/python",
      "args": ["/absolute/path/to/fred-mcp/fred_server.py"],
      "env": {
        "FRED_API_KEY": "your_fred_api_key_here"
      }
    }
  }
}
```

## Quick test

Run a protocol-level smoke test:

```bash
cd mcp-fred
.venv/bin/python - <<'PY'
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(
        command=".venv/bin/python",
        args=["fred_server.py"],
    )
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print("tool_count =", len(tools.tools))
            out = await s.call_tool("search_series", {"query": "unemployment rate", "limit": 1})
            print(out.content[0].text)

asyncio.run(main())
PY
```

## Functionality and endpoint coverage

The server includes both dedicated tools and generic passthrough tools.

### Generic passthrough

- `fred_request(endpoint, params_json)` for `/fred/*`
- `geofred_request(endpoint, params_json)` for `/geofred/*`
- `fred_v2_request(endpoint, params_json)` for `/fred/v2/*`

### FRED categories

- `get_category` -> `fred/category`
- `get_category_children` -> `fred/category/children`
- `get_category_related` -> `fred/category/related`
- `get_category_series` -> `fred/category/series`
- `get_category_tags` -> `fred/category/tags`
- `get_category_related_tags` -> `fred/category/related_tags`

### FRED releases

- `get_releases` -> `fred/releases`
- `get_releases_dates` -> `fred/releases/dates`
- `get_release` -> `fred/release`
- `get_release_dates` -> `fred/release/dates`
- `get_release_series` -> `fred/release/series`
- `get_release_sources` -> `fred/release/sources`
- `get_release_tags` -> `fred/release/tags`
- `get_release_related_tags` -> `fred/release/related_tags`
- `get_release_tables` -> `fred/release/tables`

### FRED series

- `get_series` -> `fred/series`
- `get_series_categories` -> `fred/series/categories`
- `get_observations` -> `fred/series/observations`
- `get_series_observations` -> alias of `get_observations`
- `get_series_release` -> `fred/series/release`
- `search_series` -> `fred/series/search`
- `search_series_by_tags` -> `fred/series/search/tags`
- `search_series_related_tags` -> `fred/series/search/related_tags`
- `get_series_tags` -> `fred/series/tags`
- `get_series_updates` -> `fred/series/updates`
- `get_series_vintage_dates` -> `fred/series/vintagedates`

### FRED sources

- `get_sources` -> `fred/sources`
- `get_source` -> `fred/source`
- `get_source_releases` -> `fred/source/releases`

### FRED tags

- `get_tags` -> `fred/tags`
- `get_related_tags` -> `fred/related_tags`
- `get_tag_series` -> `fred/tags/series`

### GeoFRED maps

- `get_map_shape_file` -> `geofred/shapes/file`
- `get_map_series_group` -> `geofred/series/group`
- `get_map_series_data` -> `geofred/series/data`
- `get_map_regional_data` -> `geofred/regional/data`

### FRED v2

- `get_release_observations_v2` -> `fred/v2/release/observations`

## Common examples

- Search: `search_series("unemployment rate", limit=5)`
- Observations with transform: `get_observations("CPIAUCSL", observation_start="2024-01-01", units="pc1", limit=12)`
- Category browsing: `get_category_children(0)`
- Release exploration: `get_releases(limit=10)`
- Raw endpoint call: `fred_request("series/observations", "{\"series_id\":\"UNRATE\",\"limit\":3}")`
