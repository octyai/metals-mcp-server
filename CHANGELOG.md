# Changelog

All notable changes to metals-mcp-server are documented here.

## [Unreleased] — Production Hardening (001-baseline-spec)

### Must-Fix

- **M1** `app.py`: `AuthorizationError` now returns `401 Unauthorized` with `WWW-Authenticate: Bearer` header instead of being swallowed as `500`. Affects both `handle_post` and `handle_stream`.
- **M2** `storage/sqlite_store.py`: Added `busy_timeout=30000` (30s) to all connections and `checkpoint()` method calling `PRAGMA wal_checkpoint(TRUNCATE)`. Service calls `checkpoint()` after every `ingest_sources` cycle.
- **M3** `.gitignore`, `Makefile`: Added exclusions for `__pycache__/`, `*.pyc`, `*.db`, `data/raw/`, `data/reports/`. README updated to note that `data/metals_mcp.db` and `data/raw/` are excluded from distribution tarball.

### Should-Fix

- **S1** `analytics/scenario.py`, `service.py`, templates: All scenario engine outputs now include `"disclaimer": "Illustrative only. Sensitivities are not calibrated against historical data."`. All 6 report templates render the disclaimer as a `> [!warning]` callout.
- **S2** `storage/sqlite_store.py`: WAL growth bounded by checkpoint after each ingest cycle.
- **S3** `adapters/gdelt.py`, `config.py`: GDELT `maxrecords` is now configurable via `METALS_MCP_GDELT_MAX_RECORDS` env var (default 25).
- **S4** `adapters/cme.py`: `CMEQuoteAdapter._parse_html()` logs a warning when no price patterns match, surfaced in `summary.warnings`.
- **S5** `adapters/fred.py`, `adapters/gdelt.py`: Both adapters now retry with exponential backoff on HTTP `429` and `5xx` errors (max 30s total). `backoff` package added to `requirements.txt`.
- **S6** `models/tools.py`: `Shock.pct` and `Shock.value` reject values with `|v| > 10_000` via Pydantic `field_validator`.
