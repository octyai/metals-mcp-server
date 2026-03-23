from __future__ import annotations

from typing import Any

from metals_mcp.storage.sqlite_store import SqliteStore


KEY_SERIES = [
    "cme:gold_front",
    "cme:silver_front",
    "cme:copper_front",
    "cme:platinum_front",
    "fred:dxy_major",
    "fred:real_yield_10y",
    "fred:copper_world_monthly",
]


def _format_change(latest: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    if not previous:
        return {"latest": latest, "change": None, "change_pct": None}
    change = latest["value"] - previous["value"]
    change_pct = None if previous["value"] == 0 else (change / previous["value"] * 100)
    return {"latest": latest, "previous": previous, "change": change, "change_pct": change_pct}


def build_market_snapshot(store: SqliteStore, scope: str, include: list[str]) -> dict[str, Any]:
    series = {}
    for series_id in KEY_SERIES:
        points = store.latest_series_points(series_id, limit=2)
        if not points:
            continue
        latest = points[0]
        previous = points[1] if len(points) > 1 else None
        series[series_id] = _format_change(latest, previous)
    events = store.recent_events(since_hours=168) if "news" in include or "policy" in include or "weather" in include else []
    documents = store.recent_documents(since_hours=720)
    risks: list[str] = []

    event_blob = " ".join(
        ((event.get("title") or "") + " " + (event.get("summary") or "")) for event in events
    ).lower()
    if any(term in event_blob for term in ["strike", "protest", "shutdown", "curtail", "outage"]):
        risks.append("Supply-side mine or smelter disruption risk is visible in the current public event set.")
    if any(term in event_blob for term in ["sanction", "export ban", "tariff", "royalty"]):
        risks.append("Policy and sanctions friction is elevated for metals flows or producers.")
    if any(term in event_blob for term in ["storm", "flood", "cyclone", "wildfire", "power"]):
        risks.append("Weather or power-related operational disruption risk is elevated.")

    if "cme:gold_front" in series and "cme:silver_front" in series:
        gold = series["cme:gold_front"]["latest"]["value"]
        silver = series["cme:silver_front"]["latest"]["value"]
        if silver:
            risks.append(f"Gold-silver ratio currently {gold / silver:.2f}.")
    if "cme:copper_front" in series and "fred:dxy_major" in series:
        copper = series["cme:copper_front"]["latest"]["value"]
        dxy = series["fred:dxy_major"]["latest"]["value"]
        risks.append(f"Copper front contract at {copper:.2f} with major dollar index at {dxy:.2f}.")
    return {
        "scope": scope,
        "series": series,
        "events": events[:10],
        "documents": documents[:10],
        "risks": risks,
        "source_status": store.source_status(),
    }
