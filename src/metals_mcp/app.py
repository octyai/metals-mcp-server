
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from metals_mcp.adapters.registry import AdapterRegistry
from metals_mcp.config import Settings
from metals_mcp.logging import configure_logging
from metals_mcp.mcp.router import McpRouter
from metals_mcp.mcp.session import SessionHub
from metals_mcp.service import MetalsMCPService, ServiceContext
from metals_mcp.storage.raw_archive import RawArchiveStore
from metals_mcp.storage.sqlite_store import SqliteStore

REQUEST_COUNTER = Counter("metals_mcp_http_requests_total", "HTTP requests", ["path"])
REQUEST_LATENCY = Histogram("metals_mcp_http_request_latency_seconds", "HTTP request latency", ["path"])


def create_app() -> FastAPI:
    settings = Settings.from_env()
    configure_logging(settings.debug)
    store = SqliteStore(settings.db_path)
    archive = RawArchiveStore(settings.raw_dir)
    registry = AdapterRegistry(settings)
    service = MetalsMCPService(ServiceContext(settings=settings, registry=registry, store=store, archive=archive))
    sessions = SessionHub()
    app = FastAPI(title="metals-mcp-server", version="0.1.0")
    app.state.settings = settings
    app.state.store = store
    app.state.archive = archive
    app.state.registry = registry
    app.state.service = service
    app.state.sessions = sessions

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        REQUEST_COUNTER.labels(path="/healthz").inc()
        return {"status": "ok"}

    @app.get("/metrics")
    def metrics() -> PlainTextResponse:
        return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)

    @app.post("/admin/bootstrap")
    def bootstrap() -> dict[str, object]:
        return {"summaries": service.ingest_sources(all_sources=True)}

    mcp_router = McpRouter(service=service, session_hub=sessions, settings=settings)
    app.include_router(mcp_router.router)
    return app
