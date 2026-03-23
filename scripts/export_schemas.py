from __future__ import annotations

import json
from pathlib import Path

from metals_mcp.models.canonical import DocumentRecord, EventRecord, ObservationRecord, ReportArtifact
from metals_mcp.models.common import SourceManifest, SourceArtifact, ValidationResult
from metals_mcp.models.mcp import JsonRpcRequest, JsonRpcResponse, McpPrompt, McpResource
from metals_mcp.models.tools import (
    GenerateReportRequest,
    GetAssetStatusRequest,
    GetMarketSnapshotRequest,
    IngestSourceRequest,
    QuerySeriesRequest,
    RunScenarioRequest,
    SearchMetalsEventsRequest,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "schemas" / "generated"
OUT.mkdir(parents=True, exist_ok=True)

MODELS = {
    "SourceManifest": SourceManifest,
    "SourceArtifact": SourceArtifact,
    "ValidationResult": ValidationResult,
    "ObservationRecord": ObservationRecord,
    "EventRecord": EventRecord,
    "DocumentRecord": DocumentRecord,
    "ReportArtifact": ReportArtifact,
    "JsonRpcRequest": JsonRpcRequest,
    "JsonRpcResponse": JsonRpcResponse,
    "McpResource": McpResource,
    "McpPrompt": McpPrompt,
    "QuerySeriesRequest": QuerySeriesRequest,
    "GetMarketSnapshotRequest": GetMarketSnapshotRequest,
    "SearchMetalsEventsRequest": SearchMetalsEventsRequest,
    "GenerateReportRequest": GenerateReportRequest,
    "RunScenarioRequest": RunScenarioRequest,
    "GetAssetStatusRequest": GetAssetStatusRequest,
    "IngestSourceRequest": IngestSourceRequest,
}

for name, model in MODELS.items():
    schema = model.model_json_schema()
    (OUT / f"{name}.schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")

index = {name: f"generated/{name}.schema.json" for name in MODELS}
(ROOT / "schemas" / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
print(f"exported {len(MODELS)} schemas to {OUT}")
