
from __future__ import annotations

from typing import Any

from metals_mcp.adapters.base import SourceAdapter
from metals_mcp.models.canonical import EventRecord
from metals_mcp.models.common import Provenance, RawPayload, SourceArtifact
from metals_mcp.utils import now_utc, parse_datetime, stable_hash


class NWSAlertsAdapter(SourceAdapter):
    def discover(self) -> list[SourceArtifact]:
        if self.use_fixtures():
            items = self.load_fixture_json("discover.json")
            return [SourceArtifact(source_id=self.manifest.source_id, **item) for item in items]
        url = self.manifest.settings.get("url", "https://api.weather.gov/alerts/active?status=actual&message_type=alert")
        return [SourceArtifact(source_id=self.manifest.source_id, artifact_id="active_alerts", kind="geojson", url=url)]

    def fetch(self, artifact: SourceArtifact) -> RawPayload:
        if self.use_fixtures():
            data = self.load_fixture_json("active_alerts.json")
            return RawPayload(source_id=self.manifest.source_id, artifact_id=artifact.artifact_id, retrieved_at=now_utc(), data=data)
        response = self._http.get(artifact.url, headers={"Accept": "application/geo+json"})
        response.raise_for_status()
        return RawPayload(source_id=self.manifest.source_id, artifact_id=artifact.artifact_id, retrieved_at=now_utc(), data=response.json())

    def parse(self, payload: RawPayload) -> list[dict[str, Any]]:
        data = payload.data or {}
        if isinstance(data, dict):
            return data.get("features", [])
        return []

    def normalize(self, parsed: list[dict[str, Any]], payload: RawPayload) -> list[EventRecord]:
        events: list[EventRecord] = []
        for feature in parsed:
            properties = feature.get("properties", {})
            event_id = properties.get("id") or stable_hash(properties)
            events.append(
                EventRecord(
                    source_id=self.manifest.source_id,
                    event_id=event_id,
                    title=properties.get("event", "Weather Alert"),
                    summary=properties.get("headline") or properties.get("description"),
                    event_type="weather_alert",
                    severity="high" if properties.get("severity") in {"Severe", "Extreme"} else "medium",
                    geo=properties.get("areaDesc"),
                    url=properties.get("@id"),
                    published_at=parse_datetime(properties.get("sent")),
                    ingested_at=payload.retrieved_at,
                    tags=[tag for tag in [properties.get("event"), properties.get("severity"), properties.get("category")] if tag],
                    metadata=properties,
                    provenance=Provenance(
                        source_id=self.manifest.source_id,
                        source_url=properties.get("@id"),
                        source_published_at=parse_datetime(properties.get("sent")),
                        ingested_at=payload.retrieved_at,
                    ),
                )
            )
        return events
