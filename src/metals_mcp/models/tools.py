from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class QuerySeriesRequest(BaseModel):
    series_ids: list[str] = Field(min_length=1)
    start: datetime | None = None
    end: datetime | None = None
    frequency: str = "auto"
    geo: str | None = None


class GetMarketSnapshotRequest(BaseModel):
    scope: Literal["global", "us", "north_america", "latin_america", "europe", "asia", "africa"] = "global"
    as_of: datetime | None = None
    include: list[str] = Field(default_factory=lambda: ["prices", "fundamentals", "weather", "policy", "news"])


class SearchMetalsEventsRequest(BaseModel):
    query: str
    since_hours: int = 168
    geo: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class GenerateReportRequest(BaseModel):
    template: Literal[
        "intraday_market_snapshot",
        "shipping_disruption_watch",
        "storm_impact_watch",
        "sanctions_impact_watch",
        "mine_disruption_watch",
        "executive_brief",
    ] = "intraday_market_snapshot"
    scope: str = "global"
    as_of: datetime | None = None
    max_length: Literal["short", "medium", "long"] = "medium"
    scenario: dict[str, Any] | None = None


class Shock(BaseModel):
    type: Literal[
        "mine_disruption",
        "smelter_outage",
        "sanctions",
        "logistics_disruption",
        "exchange_disruption",
        "power_disruption",
        "volatility_multiplier",
    ]
    route: str | None = None
    pct: float | None = None
    value: float | None = None
    region: str | None = None
    asset: str | None = None
    description: str | None = None


class RunScenarioRequest(BaseModel):
    scenario_type: Literal["mine", "smelter", "sanctions", "logistics", "exchange", "macro"]
    shocks: list[Shock]
    horizon_days: int = 14
    target_series_ids: list[str] = Field(
        default_factory=lambda: [
            "cme:gold_front",
            "cme:silver_front",
            "cme:copper_front",
            "cme:platinum_front",
        ]
    )


class GetAssetStatusRequest(BaseModel):
    asset: str | None = None
    mine: str | None = None
    smelter: str | None = None
    warehouse: str | None = None
    port: str | None = None
    exchange: str | None = None
    route: str | None = None


class IngestSourceRequest(BaseModel):
    source_id: str | None = None
    all_sources: bool = False


class ToolEnvelope(BaseModel):
    name: str
    title: str
    description: str
    input_schema: dict[str, Any]
