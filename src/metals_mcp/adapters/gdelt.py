from __future__ import annotations

from typing import Any

from metals_mcp.adapters.base import SourceAdapter
from metals_mcp.models.canonical import EventRecord
from metals_mcp.models.common import Provenance, RawPayload, SourceArtifact
from metals_mcp.utils import now_utc, parse_datetime, stable_hash


class GDELTAdapter(SourceAdapter):
    def discover(self) -> list[SourceArtifact]:
        query = self.manifest.settings.get(
            "query",
            "(gold OR silver OR copper OR platinum OR palladium OR nickel OR zinc OR aluminium OR smelter OR mine)",
        )
        timespan = self.manifest.settings.get("timespan", "1day")
        url = self.manifest.settings.get(
            "url_template",
            "https://api.gdeltproject.org/api/v2/doc/doc?query={query}&mode=artlist&format=json&maxrecords=25&timespan={timespan}",
        ).format(query=query, timespan=timespan)
        return [SourceArtifact(source_id=self.manifest.source_id, artifact_id="gdelt_doc", kind="json", url=url, metadata={"query": query})]

    def fetch(self, artifact: SourceArtifact) -> RawPayload:
        if self.use_fixtures():
            data = self.load_fixture_json("gdelt_doc.json")
            return RawPayload(source_id=self.manifest.source_id, artifact_id=artifact.artifact_id, retrieved_at=now_utc(), data=data, metadata=artifact.metadata)
        response = self._http.get(artifact.url)
        response.raise_for_status()
        return RawPayload(source_id=self.manifest.source_id, artifact_id=artifact.artifact_id, retrieved_at=now_utc(), data=response.json(), metadata=artifact.metadata)

    def parse(self, payload: RawPayload) -> list[dict[str, Any]]:
        data = payload.data or {}
        if isinstance(data, dict):
            return data.get("articles", [])
        return []

    def normalize(self, parsed: list[dict[str, Any]], payload: RawPayload) -> list[EventRecord]:
        events: list[EventRecord] = []
        for article in parsed:
            url = article.get("url")
            title = article.get("title") or "Metals news"
            event_id = stable_hash({"url": url, "title": title})
            published = parse_datetime(article.get("seendate") or article.get("socialimage_timestamp") or article.get("domain"))
            events.append(
                EventRecord(
                    source_id=self.manifest.source_id,
                    event_id=event_id,
                    title=title,
                    summary=article.get("snippet"),
                    event_type="news",
                    severity="medium",
                    geo=article.get("sourcecountry"),
                    url=url,
                    published_at=published,
                    ingested_at=payload.retrieved_at,
                    tags=[tag for tag in [payload.metadata.get("query"), article.get("domain")] if tag],
                    metadata=article,
                    provenance=Provenance(
                        source_id=self.manifest.source_id,
                        source_url=url,
                        source_published_at=published,
                        ingested_at=payload.retrieved_at,
                    ),
                )
            )
        return events
