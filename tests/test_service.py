from __future__ import annotations

import threading
from pathlib import Path

import pytest
import httpx

from metals_mcp.models.tools import GenerateReportRequest, GetMarketSnapshotRequest, QuerySeriesRequest
from metals_mcp.service import MetalsMCPService


def test_scenario_response_includes_disclaimer(app):
    """run_scenario result includes disclaimer key with correct text."""
    service: MetalsMCPService = app.state.service
    service.ingest_sources(all_sources=True)
    from metals_mcp.models.tools import RunScenarioRequest, Shock
    request = RunScenarioRequest(
        scenario_type="mine",
        shocks=[Shock(type="mine_disruption", pct=500.0)],
        horizon_days=14,
        target_series_ids=["cme:gold_front"],
    )
    result = service.run_scenario(request)
    assert "disclaimer" in result, f"Expected disclaimer in result, got: {list(result.keys())}"
    assert result["disclaimer"] == "Illustrative only. Sensitivities are not calibrated against historical data."


def test_shock_bounds_reject_extreme_values():
    """Shock model rejects pct and value with |v| > 10_000."""
    from pydantic import ValidationError
    from metals_mcp.models.tools import Shock

    with pytest.raises(ValidationError) as exc_info:
        Shock(type="mine_disruption", pct=99999.0)
    assert "exceeds bound of 10000" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        Shock(type="mine_disruption", value=-99999.0)
    assert "exceeds bound of 10000" in str(exc_info.value)

    # Valid values within bound should pass
    shock = Shock(type="mine_disruption", pct=500.0)
    assert shock.pct == 500.0


def test_gdelt_retries_on_429():
    """GDELT and FRED adapters retry on HTTP 429/5xx via _should_retry predicate."""
    from metals_mcp.adapters.gdelt import _should_retry as gdelt_should_retry
    from metals_mcp.adapters.fred import _should_retry as fred_should_retry

    class FakeResp:
        status_code = 0

    for should_retry in (gdelt_should_retry, fred_should_retry):
        # 429 is retryable
        r = FakeResp()
        r.status_code = 429
        exc = httpx.HTTPStatusError("rate limited", request=None, response=r)
        assert should_retry(exc), f"{should_retry.__module__}: 429 should be retryable"
        # 5xx is retryable
        r.status_code = 503
        exc = httpx.HTTPStatusError("server error", request=None, response=r)
        assert should_retry(exc), f"{should_retry.__module__}: 5xx should be retryable"
        # 400 is not retryable
        r.status_code = 400
        exc = httpx.HTTPStatusError("bad request", request=None, response=r)
        assert not should_retry(exc), f"{should_retry.__module__}: 400 should not be retryable"
        # 404 is not retryable
        r.status_code = 404
        exc = httpx.HTTPStatusError("not found", request=None, response=r)
        assert not should_retry(exc), f"{should_retry.__module__}: 404 should not be retryable"


def test_cme_parser_warns_on_miss(tmp_path, monkeypatch):
    """When CME adapter encounters HTML with no price patterns, warnings are non-empty."""
    monkeypatch.setenv("METALS_MCP_MODE", "live")
    monkeypatch.setenv("METALS_MCP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("METALS_MCP_DB_PATH", str(tmp_path / "metals_mcp.db"))
    monkeypatch.setenv("METALS_MCP_GDELT_MAX_RECORDS", "25")
    from metals_mcp.app import create_app
    app = create_app()
    registry = app.state.registry
    original_adapter = registry.create("cme_metals_quotes")

    class NoPriceHTMLAdapter(original_adapter.__class__):  # type: ignore[valid-type]
        def discover(self):
            return original_adapter.discover()

        def fetch(self, artifact):
            from metals_mcp.models.common import RawPayload
            from metals_mcp.utils import now_utc
            return RawPayload(
                source_id=self.manifest.source_id,
                artifact_id=artifact.artifact_id,
                retrieved_at=now_utc(),
                text="<html><body>No price data here</body></html>",
                metadata={"series_id": "cme:gold_front", "artifact_id": artifact.artifact_id},
            )

    no_price_adapter = NoPriceHTMLAdapter(original_adapter.manifest, original_adapter.settings)
    summary = no_price_adapter.ingest_once(app.state.store, app.state.archive)
    assert len(summary.warnings) > 0, f"Expected warnings for parse miss, got: {summary.warnings}"


def test_gdelt_max_records_env(tmp_path, monkeypatch):
    """GDELT adapter uses METALS_MCP_GDELT_MAX_RECORDS value in the discovered URL."""
    monkeypatch.setenv("METALS_MCP_MODE", "fixture")
    monkeypatch.setenv("METALS_MCP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("METALS_MCP_DB_PATH", str(tmp_path / "metals_mcp.db"))
    monkeypatch.setenv("METALS_MCP_GDELT_MAX_RECORDS", "50")
    from metals_mcp.app import create_app
    app = create_app()
    registry = app.state.registry
    adapter = registry.create("gdelt_metals_events")
    artifacts = adapter.discover()
    assert len(artifacts) == 1
    assert "maxrecords=50" in artifacts[0].url, f"Expected maxrecords=50 in URL, got: {artifacts[0].url}"


def test_concurrent_ingest_succeeds(app):
    """Two simultaneous ingest_sources calls must both complete without 'database is locked'."""
    service: MetalsMCPService = app.state.service
    errors: list[str] = []

    def ingest() -> None:
        try:
            service.ingest_sources(all_sources=True)
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))

    t1 = threading.Thread(target=ingest)
    t2 = threading.Thread(target=ingest)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert not errors, f"Concurrent ingest failed: {errors}"


def test_wal_file_does_not_grow(app, tmp_path):
    """After multiple ingest cycles, WAL file size must stay below 1MB."""
    service: MetalsMCPService = app.state.service
    db_path = app.state.store.db_path
    wal_path = db_path.parent / (db_path.name + "-wal")
    for _ in range(10):
        service.ingest_sources(all_sources=True)
    if wal_path.exists():
        assert wal_path.stat().st_size < 1024 * 1024, f"WAL file grew to {wal_path.stat().st_size} bytes"


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
