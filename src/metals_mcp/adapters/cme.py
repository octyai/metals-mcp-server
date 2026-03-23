from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup

from metals_mcp.adapters.base import SourceAdapter
from metals_mcp.models.canonical import ObservationRecord
from metals_mcp.models.common import Provenance, RawPayload, SourceArtifact
from metals_mcp.utils import now_utc, parse_datetime


_NUMBER_PATTERNS = [
    re.compile(r'"last"\s*:\s*"?(?P<value>-?\d[\d,]*\.?\d*)"?', re.I),
    re.compile(r'"lastPrice"\s*:\s*"?(?P<value>-?\d[\d,]*\.?\d*)"?', re.I),
    re.compile(r'data-last\s*=\s*"(?P<value>-?\d[\d,]*\.?\d*)"', re.I),
    re.compile(r'Last(?:\s+price)?[^0-9-]{0,20}(?P<value>-?\d[\d,]*\.?\d*)', re.I),
]
_PREV_PATTERNS = [
    re.compile(r'"priorSettle"\s*:\s*"?(?P<value>-?\d[\d,]*\.?\d*)"?', re.I),
    re.compile(r'Prior(?:\s+Settle)?[^0-9-]{0,20}(?P<value>-?\d[\d,]*\.?\d*)', re.I),
]
_UPDATED_PATTERNS = [
    re.compile(r'Last Updated\s*(?P<ts>[A-Za-z0-9:,\-\s]+(?:CT|CST|CDT|UTC|GMT)?)', re.I),
    re.compile(r'"updated"\s*:\s*"(?P<ts>[^"]+)"', re.I),
]


class CMEQuoteAdapter(SourceAdapter):
    def discover(self) -> list[SourceArtifact]:
        items = self.manifest.settings.get("series", [])
        if self.use_fixtures():
            items = self.load_fixture_json("discover.json")
        return [SourceArtifact(source_id=self.manifest.source_id, **item) for item in items]

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
        if not artifact.url:
            raise RuntimeError(f"CME artifact {artifact.artifact_id} missing url")
        response = self._http.get(artifact.url)
        response.raise_for_status()
        return RawPayload(
            source_id=self.manifest.source_id,
            artifact_id=artifact.artifact_id,
            retrieved_at=now_utc(),
            content_type=response.headers.get("content-type", "text/html"),
            text=response.text,
            metadata={**artifact.metadata, "url": artifact.url},
        )

    def parse(self, payload: RawPayload) -> list[dict[str, Any]]:
        if payload.data is not None:
            if isinstance(payload.data, dict):
                if "quotes" in payload.data:
                    return payload.data["quotes"]
                return [payload.data]
            if isinstance(payload.data, list):
                return payload.data
        text = payload.text or ""
        if not text:
            return []
        parsed = self._parse_html(text)
        return [parsed] if parsed else []

    def _parse_html(self, text: str) -> dict[str, Any] | None:
        soup = BeautifulSoup(text, "html.parser")
        value = None
        previous = None
        observed_at = None

        # first try machine-readable script blocks
        for script in soup.find_all("script"):
            raw = script.string or script.get_text(" ", strip=True)
            if not raw:
                continue
            candidate = self._search_patterns(raw, _NUMBER_PATTERNS)
            if candidate is not None:
                value = candidate
                previous = self._search_patterns(raw, _PREV_PATTERNS)
                observed_at = self._search_timestamp(raw)
                break

        if value is None:
            text_blob = soup.get_text(" ", strip=True)
            value = self._search_patterns(text_blob, _NUMBER_PATTERNS)
            previous = self._search_patterns(text_blob, _PREV_PATTERNS)
            observed_at = self._search_timestamp(text_blob)

        if value is None:
            return None
        row: dict[str, Any] = {"value": value}
        if previous is not None:
            row["previous"] = previous
        if observed_at is not None:
            row["observed_at"] = observed_at
        return row

    def _search_patterns(self, text: str, patterns: list[re.Pattern[str]]) -> float | None:
        for pattern in patterns:
            match = pattern.search(text)
            if not match:
                continue
            raw = match.group("value")
            try:
                return float(raw.replace(",", ""))
            except Exception:
                continue
        return None

    def _search_timestamp(self, text: str):
        for pattern in _UPDATED_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            ts = match.group("ts")
            dt = parse_datetime(ts)
            if dt is not None:
                return dt
        return None

    def normalize(self, parsed: list[dict[str, Any]], payload: RawPayload) -> list[ObservationRecord]:
        records: list[ObservationRecord] = []
        meta = payload.metadata
        for row in parsed:
            value = row.get("value")
            if value in (None, "", "."):
                continue
            observed_at = parse_datetime(str(row.get("observed_at"))) or payload.retrieved_at
            previous = row.get("previous")
            metadata = dict(row)
            if previous is not None:
                metadata["change"] = float(value) - float(previous)
            records.append(
                ObservationRecord(
                    source_id=self.manifest.source_id,
                    series_id=meta.get("series_id", payload.artifact_id),
                    label=meta.get("label", payload.artifact_id),
                    observed_at=observed_at,
                    published_at=observed_at,
                    ingested_at=payload.retrieved_at,
                    value=float(value),
                    unit=meta.get("unit", "price"),
                    geo=meta.get("geo"),
                    commodity=meta.get("commodity", "metals"),
                    frequency=meta.get("frequency", "intraday_delayed"),
                    metadata=metadata,
                    provenance=Provenance(
                        source_id=self.manifest.source_id,
                        source_url=payload.metadata.get("url") or meta.get("source_url") or meta.get("url"),
                        source_published_at=observed_at,
                        ingested_at=payload.retrieved_at,
                    ),
                )
            )
        return records
