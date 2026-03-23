from __future__ import annotations

from metals_mcp.models.tools import (
    GenerateReportRequest,
    GetAssetStatusRequest,
    GetMarketSnapshotRequest,
    IngestSourceRequest,
    QuerySeriesRequest,
    RunScenarioRequest,
    SearchMetalsEventsRequest,
    ToolEnvelope,
)


def tool_catalog() -> list[ToolEnvelope]:
    return [
        ToolEnvelope(
            name="query_series",
            title="Query time series",
            description="Query normalized metals time series.",
            input_schema=QuerySeriesRequest.model_json_schema(),
        ),
        ToolEnvelope(
            name="get_market_snapshot",
            title="Get market snapshot",
            description="Return a normalized metals market snapshot.",
            input_schema=GetMarketSnapshotRequest.model_json_schema(),
        ),
        ToolEnvelope(
            name="search_metals_events",
            title="Search metals events",
            description="Search normalized public metals events.",
            input_schema=SearchMetalsEventsRequest.model_json_schema(),
        ),
        ToolEnvelope(
            name="generate_report",
            title="Generate report",
            description="Generate a grounded markdown report.",
            input_schema=GenerateReportRequest.model_json_schema(),
        ),
        ToolEnvelope(
            name="run_scenario",
            title="Run scenario",
            description="Run a deterministic metals scenario model.",
            input_schema=RunScenarioRequest.model_json_schema(),
        ),
        ToolEnvelope(
            name="get_asset_status",
            title="Get asset status",
            description="Search for mine, smelter, exchange, warehouse, or route context.",
            input_schema=GetAssetStatusRequest.model_json_schema(),
        ),
        ToolEnvelope(
            name="ingest_source",
            title="Ingest sources",
            description="Trigger fixture or live ingestion.",
            input_schema=IngestSourceRequest.model_json_schema(),
        ),
    ]
