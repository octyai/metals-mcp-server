from __future__ import annotations

from typing import Any

from metals_mcp.adapters.base import SourceAdapter
from metals_mcp.models.canonical import ObservationRecord
from metals_mcp.models.common import Provenance, RawPayload, SourceArtifact
from metals_mcp.utils import now_utc, parse_datetime


class FredAdapter(SourceAdapter):
    def discover(self) -> list[SourceArtifact]:
        series = self.manifest.settings.get("series", [])
        if self.use_fixtures():
            series = self.load_fixture_json("discover.json")
        return [SourceArtifact(source_id=self.manifest.source_id, **item) for item in series]

    def fetch(self, artifact: SourceArtifact) -> RawPayload:
        if self.use_fixtures():
            data = self.load_fixture_json(f"{artifact.artifact_id}.json")
            return RawPayload(
                source_id=self.manifest.source_id,
                artifact_id=artifact.artifact_id,
                retrieved_at=now_utc(),
                data=data,
                metadata=artifact.metadata,
            )
        if not self.settings.fred_api_key:
            raise RuntimeError("METALS_MCP_FRED_API_KEY is required for live FRED ingestion")
        url = artifact.url.format(api_key=self.settings.fred_api_key) if artifact.url else None
        if not url:
            raise RuntimeError(f"FRED artifact {artifact.artifact_id} missing url")
        response = self._http.get(url)
        response.raise_for_status()
        return RawPayload(
            source_id=self.manifest.source_id,
            artifact_id=artifact.artifact_id,
            retrieved_at=now_utc(),
            data=response.json(),
            metadata=artifact.metadata,
        )

    def parse(self, payload: RawPayload) -> list[dict[str, Any]]:
        data = payload.data or {}
        if isinstance(data, dict):
            return data.get("observations", [])
        return []

    def normalize(self, parsed: list[dict[str, Any]], payload: RawPayload) -> list[ObservationRecord]:
        records: list[ObservationRecord] = []
        meta = payload.metadata
        for row in parsed:
            value = row.get("value")
            if value in (None, "", "."):
                continue
            observed_at = parse_datetime(row.get("date"))
            if observed_at is None:
                continue
            records.append(
                ObservationRecord(
                    source_id=self.manifest.source_id,
                    series_id=meta.get("series_id", payload.artifact_id),
                    label=meta.get("label", payload.artifact_id),
                    observed_at=observed_at,
                    published_at=observed_at,
                    ingested_at=payload.retrieved_at,
                    value=float(value),
                    unit=meta.get("unit", "index"),
                    geo=meta.get("geo"),
                    commodity=meta.get("commodity", "metals"),
                    frequency=meta.get("frequency", "daily"),
                    metadata=row,
                    provenance=Provenance(
                        source_id=self.manifest.source_id,
                        source_url=meta.get("source_url") or meta.get("url"),
                        source_published_at=observed_at,
                        ingested_at=payload.retrieved_at,
                    ),
                )
            )
        return records
