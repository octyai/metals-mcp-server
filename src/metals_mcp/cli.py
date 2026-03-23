from __future__ import annotations

import argparse
import json

import uvicorn

from metals_mcp.adapters.registry import AdapterRegistry
from metals_mcp.app import create_app
from metals_mcp.config import Settings
from metals_mcp.service import MetalsMCPService, ServiceContext
from metals_mcp.storage.raw_archive import RawArchiveStore
from metals_mcp.storage.sqlite_store import SqliteStore


def build_service() -> MetalsMCPService:
    settings = Settings.from_env()
    store = SqliteStore(settings.db_path)
    archive = RawArchiveStore(settings.raw_dir)
    registry = AdapterRegistry(settings)
    return MetalsMCPService(ServiceContext(settings=settings, registry=registry, store=store, archive=archive))


def main() -> None:
    parser = argparse.ArgumentParser(prog="metals-mcp")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Run the MCP server")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)

    ingest = sub.add_parser("ingest", help="Ingest one or more sources")
    ingest.add_argument("--source", default=None)
    ingest.add_argument("--all", action="store_true")

    report = sub.add_parser("report", help="Generate a report")
    report.add_argument("--template", default="intraday_market_snapshot")
    report.add_argument("--scope", default="global")

    query = sub.add_parser("query", help="Query a normalized series")
    query.add_argument("series_id", nargs="+")

    args = parser.parse_args()
    settings = Settings.from_env()
    if args.command == "serve":
        uvicorn.run("metals_mcp.app:create_app", factory=True, host=args.host or settings.host, port=args.port or settings.port, reload=settings.debug)
        return

    service = build_service()
    if args.command == "ingest":
        output = service.ingest_sources(source_id=args.source, all_sources=args.all)
        print(json.dumps(output, indent=2, default=str))
        return
    if args.command == "report":
        from metals_mcp.models.tools import GenerateReportRequest

        output = service.generate_report(GenerateReportRequest(template=args.template, scope=args.scope))
        print(output["markdown"])
        return
    if args.command == "query":
        from metals_mcp.models.tools import QuerySeriesRequest

        output = service.query_series(QuerySeriesRequest(series_ids=args.series_id))
        print(json.dumps(output, indent=2, default=str))
        return


if __name__ == "__main__":
    main()
