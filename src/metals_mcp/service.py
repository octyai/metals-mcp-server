from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from jinja2 import Environment, FileSystemLoader, select_autoescape

from metals_mcp.adapters.registry import AdapterRegistry
from metals_mcp.analytics.scenario import ScenarioEngine
from metals_mcp.analytics.snapshot import build_market_snapshot
from metals_mcp.config import Settings
from metals_mcp.exceptions import NotFoundError
from metals_mcp.models.canonical import ReportArtifact
from metals_mcp.models.mcp import McpPrompt, McpResource
from metals_mcp.models.tools import (
    GenerateReportRequest,
    GetAssetStatusRequest,
    GetMarketSnapshotRequest,
    QuerySeriesRequest,
    RunScenarioRequest,
    SearchMetalsEventsRequest,
)
from metals_mcp.storage.raw_archive import RawArchiveStore
from metals_mcp.storage.sqlite_store import SqliteStore
from metals_mcp.utils import now_utc


@dataclass(slots=True)
class ServiceContext:
    settings: Settings
    registry: AdapterRegistry
    store: SqliteStore
    archive: RawArchiveStore


class MetalsMCPService:
    def __init__(self, ctx: ServiceContext) -> None:
        self.ctx = ctx
        template_root = Path(__file__).resolve().parent / "templates"
        self.templates = Environment(
            loader=FileSystemLoader(template_root),
            autoescape=select_autoescape(enabled_extensions=("html", "xml"), default_for_string=False),
        )
        self.scenario_engine = ScenarioEngine(self.ctx.store)

    def ingest_sources(self, source_id: str | None = None, all_sources: bool = False) -> list[dict[str, Any]]:
        source_ids = [source_id] if source_id else []
        if all_sources or not source_ids:
            source_ids = [manifest.source_id for manifest in self.ctx.registry.list_manifests()]
        summaries: list[dict[str, Any]] = []
        for sid in source_ids:
            adapter = self.ctx.registry.create(sid)
            try:
                summary = adapter.ingest_once(self.ctx.store, self.ctx.archive)
                summaries.append(summary.model_dump())
            finally:
                adapter.close()
        self.ctx.store.checkpoint()
        return summaries

    def query_series(self, request: QuerySeriesRequest) -> dict[str, Any]:
        return {
            "series": self.ctx.store.query_series(
                request.series_ids,
                start=request.start,
                end=request.end,
                geo=request.geo,
            )
        }

    def get_market_snapshot(self, request: GetMarketSnapshotRequest) -> dict[str, Any]:
        return build_market_snapshot(self.ctx.store, request.scope, request.include)

    def search_events(self, request: SearchMetalsEventsRequest) -> dict[str, Any]:
        return {
            "events": self.ctx.store.search_events(
                query=request.query,
                since_hours=request.since_hours,
                sources=request.sources or None,
            )
        }

    def run_scenario(self, request: RunScenarioRequest) -> dict[str, Any]:
        return self.scenario_engine.run(request)

    def get_asset_status(self, request: GetAssetStatusRequest) -> dict[str, Any]:
        query_terms = [
            term
            for term in [
                request.asset,
                request.mine,
                request.smelter,
                request.warehouse,
                request.port,
                request.exchange,
                request.route,
            ]
            if term
        ]
        if not query_terms:
            return {"assets": [], "events": [], "documents": []}
        query = " ".join(query_terms)
        return {
            "query": query,
            "events": self.ctx.store.search_events(query=query, since_hours=720),
            "documents": [
                doc
                for doc in self.ctx.store.recent_documents(since_hours=720)
                if query.lower() in (doc.get("title", "") + " " + (doc.get("summary") or "")).lower()
            ],
        }

    def generate_report(self, request: GenerateReportRequest) -> dict[str, Any]:
        snapshot = build_market_snapshot(
            self.ctx.store,
            request.scope,
            ["prices", "fundamentals", "weather", "policy", "news"],
        )
        scenario = self.scenario_engine.run(RunScenarioRequest.model_validate(request.scenario)) if request.scenario else None
        recent_documents = self.ctx.store.recent_documents(since_hours=720)
        template = self.templates.get_template(f"report_{request.template}.md.j2")
        payload = {
            "generated_at": now_utc().isoformat(),
            "snapshot": snapshot,
            "scenario": scenario,
            "scenario_disclaimer": "Illustrative only. Sensitivities are not calibrated against historical data.",
            "recent_documents": recent_documents[:10],
            "max_length": request.max_length,
        }
        markdown = template.render(**payload)
        artifact = ReportArtifact(
            report_id=str(uuid4()),
            template_name=request.template,
            created_at=now_utc(),
            scope=request.scope,
            payload=payload,
            markdown=markdown,
            citations=[event.get("url") for event in snapshot.get("events", []) if event.get("url")],
        )
        self.ctx.store.save_report(artifact)
        output = artifact.model_dump(mode="json")
        output["markdown"] = markdown
        return output

    def list_resources(self) -> list[McpResource]:
        return [
            McpResource(uri="metals://catalog/sources", name="Source catalog", description="Registered public metals sources"),
            McpResource(uri="metals://status/sources", name="Source status", description="Current ingestion status by source"),
            McpResource(uri="metals://events/active", name="Active events", description="Recent public metals events"),
            McpResource(uri="metals://documents/recent", name="Recent documents", description="Recently discovered public documents"),
            McpResource(uri="metals://reports/latest", name="Latest reports", description="Most recently generated reports"),
            McpResource(uri="metals://series/cme:gold_front", name="Gold front contract", description="Canonical delayed gold front quote"),
            McpResource(uri="metals://series/cme:silver_front", name="Silver front contract", description="Canonical delayed silver front quote"),
            McpResource(uri="metals://series/cme:copper_front", name="Copper front contract", description="Canonical delayed copper front quote"),
            McpResource(uri="metals://series/cme:platinum_front", name="Platinum front contract", description="Canonical delayed platinum front quote"),
        ]

    def read_resource(self, uri: str) -> dict[str, Any]:
        if uri == "metals://catalog/sources":
            return {"sources": [manifest.model_dump(mode="json") for manifest in self.ctx.registry.list_manifests()]}
        if uri == "metals://status/sources":
            return {"sources": self.ctx.store.source_status()}
        if uri == "metals://events/active":
            return {"events": self.ctx.store.recent_events()}
        if uri == "metals://documents/recent":
            return {"documents": self.ctx.store.recent_documents()}
        if uri == "metals://reports/latest":
            return {"reports": self.ctx.store.latest_reports()}
        if uri.startswith("metals://series/"):
            series_id = uri.removeprefix("metals://series/")
            return {"series_id": series_id, "points": self.ctx.store.query_series([series_id]).get(series_id, [])}
        if uri.startswith("metals://report/"):
            report_id = uri.removeprefix("metals://report/")
            report = self.ctx.store.get_report(report_id)
            if not report:
                raise NotFoundError(f"Unknown report: {report_id}")
            return report
        raise NotFoundError(f"Unknown resource URI: {uri}")

    def list_prompts(self) -> list[McpPrompt]:
        return [
            McpPrompt(
                name="metals_daily_market_brief",
                title="Metals daily market brief",
                description="Grounded daily metals market summary",
                arguments=[{"name": "scope", "required": False}],
            ),
            McpPrompt(
                name="metals_flash_disruption_brief",
                title="Metals disruption brief",
                description="Operational disruption, mine outage, or exchange risk report",
                arguments=[{"name": "scenario_json", "required": False}],
            ),
            McpPrompt(
                name="metals_exec_summary",
                title="Executive summary",
                description="Executive-ready metals market summary",
                arguments=[{"name": "scope", "required": False}],
            ),
        ]

    def get_prompt(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        arguments = arguments or {}
        if name == "metals_daily_market_brief":
            text = "Summarize the latest metals market changes, citing gold, silver, copper and platinum moves, mining or smelting disruptions, policy changes, and top public events. Scope: {{ scope }}."
        elif name == "metals_flash_disruption_brief":
            text = "Write a flash report on the metals disruption using recent events, source status, and scenario output. Scenario: {{ scenario_json }}."
        elif name == "metals_exec_summary":
            text = "Generate an executive summary of metals market state, key risks, and what changed from the previous cycle. Scope: {{ scope }}."
        else:
            raise NotFoundError(f"Unknown prompt: {name}")
        rendered = self.templates.from_string(text).render(**arguments)
        return {
            "description": f"Prompt template: {name}",
            "messages": [
                {
                    "role": "user",
                    "content": {"type": "text", "text": rendered},
                }
            ],
        }
