from __future__ import annotations

from metals_mcp.models.tools import RunScenarioRequest
from metals_mcp.storage.sqlite_store import SqliteStore


class ScenarioEngine:
    DEFAULTS = {
        "cme:gold_front": 2350.0,
        "cme:silver_front": 31.0,
        "cme:copper_front": 4.55,
        "cme:platinum_front": 1005.0,
        "cme:palladium_front": 1125.0,
    }
    SENSITIVITY = {
        "mine_disruption": {
            "cme:gold_front": 0.045,
            "cme:silver_front": 0.060,
            "cme:copper_front": 0.085,
            "cme:platinum_front": 0.090,
            "cme:palladium_front": 0.105,
        },
        "smelter_outage": {
            "cme:gold_front": 0.010,
            "cme:silver_front": 0.030,
            "cme:copper_front": 0.075,
            "cme:platinum_front": 0.040,
            "cme:palladium_front": 0.050,
        },
        "sanctions": {
            "cme:gold_front": 0.020,
            "cme:silver_front": 0.028,
            "cme:copper_front": 0.040,
            "cme:platinum_front": 0.060,
            "cme:palladium_front": 0.070,
        },
        "logistics_disruption": {
            "cme:gold_front": 0.008,
            "cme:silver_front": 0.016,
            "cme:copper_front": 0.045,
            "cme:platinum_front": 0.030,
            "cme:palladium_front": 0.035,
        },
        "exchange_disruption": {
            "cme:gold_front": 0.015,
            "cme:silver_front": 0.020,
            "cme:copper_front": 0.025,
            "cme:platinum_front": 0.025,
            "cme:palladium_front": 0.030,
        },
        "power_disruption": {
            "cme:gold_front": 0.005,
            "cme:silver_front": 0.012,
            "cme:copper_front": 0.050,
            "cme:platinum_front": 0.020,
            "cme:palladium_front": 0.025,
        },
        "volatility_multiplier": {
            "cme:gold_front": 0.035,
            "cme:silver_front": 0.045,
            "cme:copper_front": 0.030,
            "cme:platinum_front": 0.040,
            "cme:palladium_front": 0.045,
        },
    }

    def __init__(self, store: SqliteStore) -> None:
        self.store = store

    def _baseline(self, series_id: str) -> float:
        points = self.store.latest_series_points(series_id, limit=1)
        if points:
            return float(points[0]["value"])
        return self.DEFAULTS.get(series_id, 100.0)

    def run(self, request: RunScenarioRequest) -> dict[str, object]:
        assumptions: list[str] = []
        impacted_assets: list[str] = []
        ranges: dict[str, dict[str, float]] = {}
        baselines: dict[str, float] = {series_id: self._baseline(series_id) for series_id in request.target_series_ids}

        for series_id, baseline in baselines.items():
            delta = 0.0
            for shock in request.shocks:
                magnitude = (shock.pct or shock.value or 0.0) / 100.0
                if shock.type == "volatility_multiplier":
                    magnitude = max((shock.value or 1.0) - 1.0, 0.0)
                sensitivity = self.SENSITIVITY.get(shock.type, {}).get(series_id, 0.015)
                delta += baseline * sensitivity * magnitude
                if shock.asset:
                    impacted_assets.append(shock.asset)
                elif shock.route:
                    impacted_assets.append(shock.route)
                elif shock.region:
                    impacted_assets.append(shock.region)
                assumptions.append(
                    f"{shock.type} shock applied to {series_id} with sensitivity {sensitivity:.3f}"
                )
            central = baseline + delta
            ranges[series_id] = {
                "low": round(max(0, central * 0.94), 4),
                "central": round(central, 4),
                "high": round(central * 1.09, 4),
            }

        return {
            "scenario_type": request.scenario_type,
            "baselines": {key: round(value, 4) for key, value in baselines.items()},
            "price_ranges": ranges,
            "impacted_assets": sorted(set(impacted_assets)),
            "assumptions": assumptions,
            "horizon_days": request.horizon_days,
            "disclaimer": "Illustrative only. Sensitivities are not calibrated against historical data.",
        }
