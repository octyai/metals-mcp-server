# metals-mcp-server Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-24

## Active Technologies

- **Language**: Python 3.11+
- **Web**: FastAPI 0.111+, uvicorn 0.30+
- **HTTP**: httpx 0.28+
- **Data**: pydantic 2.8+, jsonschema 4.23+, orjson 3.10+
- **Scraping**: beautifulsoup4 4.12+
- **Templating**: Jinja2 3.1+, PyYAML 6+
- **Testing**: pytest 8+, pytest-cov 5+, ruff 0.6+
- **Optional**: psycopg[binary] 3.2+, redis 5+, clickhouse-connect 0.8+

## Project Structure

```
src/metals_mcp/
├── adapters/        # One file per adapter (cme.py, fred.py, gdelt.py, nws.py, sec.py, usgs.py, lbma.py, lme.py)
├── analytics/       # snapshot.py, scenario.py
├── mcp/             # router.py (auth handling)
├── models/          # tools.py (Pydantic request/response models)
├── storage/         # sqlite_store.py
├── service.py       # MetalsMCPService
├── app.py           # FastAPI app, exception handlers
├── config.py        # Settings (pydantic BaseSettings)
└── cli.py           # CLI entry point

schemas/generated/   # JSON schemas exported from Pydantic models
tests/
data/               # .gitignore: .db, raw/, reports/
fixtures/           # Fixture data per source_id
```

## Commands

```bash
# Run tests (fixture mode, no env vars required)
PYTHONPATH=src pytest -q

# Lint
PYTHONPATH=src ruff check .

# Type check
PYTHONPATH=src mypy src/

# Export schemas after model changes
PYTHONPATH=src python scripts/export_schemas.py

# Run server (fixture mode)
PYTHONPATH=src uvicorn metals_mcp.app:app --reload

# Build tarball (excludes generated artifacts)
make tar
```

## Code Style

- Python 3.11+: standard library conventions + ruff
- Adapter contract: `discover → fetch → parse → normalize → validate → ingest_once`
- No adapter may import another adapter
- All SQL scoped to `SqliteStore` — no business logic in SQL
- Scenario engine output must always include `disclaimer` field

## Constitution (Core Principles)

1. **Fixture-First**: All changes must preserve fixture mode. Integration tests must pass in fixture mode.
2. **Adapter Isolation**: Each source is a `SourceAdapter`. No cross-adapter imports.
3. **Scenario Illustrative**: All scenario output includes `"disclaimer": "Illustrative only. Sensitivities are not calibrated against historical data."`
4. **MCP Compatible**: `protocolVersion: 2025-11-25`. No non-standard JSON-RPC methods.
5. **Storage Portable**: SQLite default. Store interface allows Postgres swap without adapter changes.
6. **Observability**: Prometheus metrics always registered. `/healthz` and `/metrics` always available.

## Recent Changes

- 001-baseline-spec (2026-03-24): All 9 hardening fixes implemented (M1–M3, S1–S6). Auth 401, SQLite WAL checkpoint, tarball hygiene, scenario disclaimers, GDELT max_records env, CME parse warnings, backoff retry, shock bounds. All 14 tests green. Zero new lint errors in changed files.

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
