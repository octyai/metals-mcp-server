# metals-mcp-server

A production-oriented Model Context Protocol (MCP) server for public metals intelligence.

The repo ships with:
- a working MCP-compatible HTTP server
- fixture-mode ingestion so the stack works out of the box without API keys
- live adapters for major public sources where practical
- a normalized SQLite-backed data model for local development
- JSON schemas for tool inputs, MCP payloads, and canonical records
- report generation, scenario modeling, source discovery, and tests
- Docker and docker-compose support

## Current implementation status

This repo is runnable immediately in **fixture mode** and extensible for **live mode**. The local default stack uses SQLite + file-based raw archive to minimize friction. The compose file also includes Postgres, Redis, and ClickHouse services so the repository can be evolved into a larger production deployment without changing the MCP surface.

The current build focuses on:
- precious metals: gold, silver, platinum, palladium
- base metals: copper, with LME and USGS discovery surfaces for broader industrial coverage
- mining, smelting, weather, logistics, policy, and sanctions context

## Implemented sources

### Structured / semi-structured adapters
- CME delayed quote pages for gold, silver, copper, platinum, and palladium
- FRED macro and metals overlays
- National Weather Service active alerts
- GDELT metals-news event feed
- SEC submissions for tracked mining and metals companies

### Generic public-document discovery adapters
- USGS mineral commodity summaries and commodity pages
- LBMA precious metal benchmark and licensing pages
- LME market pages
- LME notices and circulars

## Repo layout

```text
.
├── src/metals_mcp
│   ├── adapters/
│   ├── analytics/
│   ├── fixtures/
│   ├── mcp/
│   ├── models/
│   ├── resources/
│   ├── storage/
│   ├── templates/
│   ├── app.py
│   ├── cli.py
│   ├── config.py
│   └── service.py
├── schemas/
│   ├── generated/
│   ├── index.json
│   └── openapi.json
├── scripts/
├── tests/
├── Dockerfile
├── docker-compose.yml
├── Makefile
└── pyproject.toml
```

## Quickstart

### 1. Create a virtualenv and install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

### 2. Run in fixture mode

```bash
cp .env.example .env
# Keep METALS_MCP_MODE=fixture for plug-and-play local boot.
uvicorn metals_mcp.app:create_app --factory --reload --port 8080
```

### 3. Bootstrap sample data

```bash
curl -X POST http://localhost:8080/admin/bootstrap
```

### 4. Talk to the MCP endpoint

Initialize:

```bash
curl -X POST http://localhost:8080/mcp \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {}
  }'
```

List tools:

```bash
curl -X POST http://localhost:8080/mcp \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {}
  }'
```

Generate a report:

```bash
curl -X POST http://localhost:8080/mcp \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "generate_report",
      "arguments": {
        "template": "intraday_market_snapshot",
        "scope": "global",
        "max_length": "medium"
      }
    }
  }'
```

## CLI

```bash
metals-mcp serve
metals-mcp ingest --all
metals-mcp report --template intraday_market_snapshot --scope global
metals-mcp query cme:gold_front cme:silver_front
```

## Live mode

Set the following in `.env`:

```bash
METALS_MCP_MODE=live
METALS_MCP_FRED_API_KEY=...
METALS_MCP_USER_AGENT=metals-mcp-server/0.1 (+your-email@example.com)
```

Some sources do not require keys but may require polite rate limiting or a descriptive user-agent. HTML discovery and quote parsers are best-effort for public pages and may need selector or regex tuning as upstream sites evolve.

## MCP surface

### Methods implemented
- `initialize`
- `notifications/initialized`
- `ping`
- `resources/list`
- `resources/read`
- `prompts/list`
- `prompts/get`
- `tools/list`
- `tools/call`

### Resources
- `metals://catalog/sources`
- `metals://status/sources`
- `metals://events/active`
- `metals://documents/recent`
- `metals://reports/latest`
- `metals://series/cme:gold_front`
- `metals://series/cme:silver_front`
- `metals://series/cme:copper_front`
- `metals://series/cme:platinum_front`

### Tools
- `query_series`
- `get_market_snapshot`
- `search_metals_events`
- `generate_report`
- `run_scenario`
- `get_asset_status`
- `ingest_source`

### Prompts
- `metals_daily_market_brief`
- `metals_flash_disruption_brief`
- `metals_exec_summary`

## Security and auth

If `METALS_MCP_AUTH_TOKENS` is set, the server requires `Authorization: Bearer <token>` on `/mcp` and the SSE stream. When auth is enabled, unauthorized requests return a `WWW-Authenticate` header pointing at `/.well-known/oauth-protected-resource`.

`METALS_MCP_ALLOWED_ORIGINS` can be used to restrict browser-originated requests.

## Validation and schemas

Pydantic enforces runtime validation for:
- source manifests
- tool arguments
- canonical records
- JSON-RPC envelopes

Generated JSON Schemas live under `schemas/generated/`.

Regenerate schemas:

```bash
PYTHONPATH=src python scripts/export_schemas.py
PYTHONPATH=src python scripts/export_openapi.py
```

## Testing

```bash
pytest
```

The current suite covers:
- fixture ingestion end to end
- report generation
- MCP initialize and tool calls
- schema export presence and parseability

## Production hardening path

The repo is structured so you can replace the local defaults with managed infrastructure while preserving the API contract:
- swap SQLite for Postgres in the storage layer
- add Redis-backed cache and rate limiter
- add ClickHouse sink for high-volume time series
- run ingestion workers separately from the MCP gateway
- attach a real OAuth authorization server
- move source manifests to a managed config store
- run scheduled ingestion under Temporal, Airflow, or a cron-based orchestrator

## Notes

- Fixture data is synthetic and intended to verify behavior and repo ergonomics.
- Public benchmark licensing varies by source. This repo stores only what the configured public source pages expose and treats benchmark documentation pages as first-class evidence surfaces alongside time-series points.
- Live HTML discovery and quote sources are intentionally generic and may need parser tuning as upstream sites change.
