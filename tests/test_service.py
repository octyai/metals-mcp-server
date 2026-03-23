from __future__ import annotations

from metals_mcp.models.tools import GenerateReportRequest, GetMarketSnapshotRequest, QuerySeriesRequest
from metals_mcp.service import MetalsMCPService


def test_bootstrap_and_query_series(app):
    service: MetalsMCPService = app.state.service
    summaries = service.ingest_sources(all_sources=True)
    assert summaries
    snapshot = service.get_market_snapshot(GetMarketSnapshotRequest())
    assert "cme:gold_front" in snapshot["series"]
    series = service.query_series(QuerySeriesRequest(series_ids=["cme:gold_front"]))
    assert series["series"]["cme:gold_front"]


def test_generate_report(app):
    service: MetalsMCPService = app.state.service
    service.ingest_sources(all_sources=True)
    report = service.generate_report(GenerateReportRequest())
    assert report["template_name"] == "intraday_market_snapshot"
    assert "Gold" in report["markdown"] or "cme:gold_front" in report["markdown"]
