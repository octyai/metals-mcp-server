
from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from metals_mcp.adapters.base import SourceAdapter
from metals_mcp.models.canonical import DocumentRecord
from metals_mcp.models.common import Provenance, RawPayload, SourceArtifact
from metals_mcp.utils import now_utc, parse_datetime, stable_hash


class GenericDocumentAdapter(SourceAdapter):
    def discover(self) -> list[SourceArtifact]:
        if self.use_fixtures():
            items = self.load_fixture_json("discover.json")
            artifacts = []
            for item in items:
                metadata = {**self.manifest.settings, **item.get("metadata", {})}
                artifacts.append(SourceArtifact(source_id=self.manifest.source_id, artifact_id=item["artifact_id"], kind=item.get("kind", "html"), url=item.get("url"), metadata=metadata))
            return artifacts
        url = self.manifest.settings["list_url"]
        return [SourceArtifact(source_id=self.manifest.source_id, artifact_id="listing", kind="html", url=url, metadata=self.manifest.settings)]

    def fetch(self, artifact: SourceArtifact) -> RawPayload:
        if self.use_fixtures():
            text = self.load_fixture_text("listing.html")
            return RawPayload(source_id=self.manifest.source_id, artifact_id=artifact.artifact_id, retrieved_at=now_utc(), content_type="text/html", text=text, metadata=artifact.metadata)
        response = self._http.get(artifact.url)
        response.raise_for_status()
        return RawPayload(source_id=self.manifest.source_id, artifact_id=artifact.artifact_id, retrieved_at=now_utc(), content_type=response.headers.get("content-type", "text/html"), text=response.text, metadata=artifact.metadata)

    def parse(self, payload: RawPayload) -> list[dict[str, Any]]:
        text = payload.text or ""
        soup = BeautifulSoup(text, "html.parser")
        selectors = payload.metadata.get("selectors", ["a"])
        allowed = payload.metadata.get("allowed_patterns", [])
        deny = payload.metadata.get("deny_patterns", [])
        base_url = payload.metadata.get("list_url") or payload.metadata.get("base_url") or self.manifest.base_url or ""
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for selector in selectors:
            for element in soup.select(selector):
                href = element.get("href")
                title = " ".join(element.get_text(" ", strip=True).split())
                if not href or not title:
                    continue
                full_url = urljoin(base_url, href)
                if allowed and not any(pattern.lower() in full_url.lower() or pattern.lower() in title.lower() for pattern in allowed):
                    continue
                if deny and any(pattern.lower() in full_url.lower() or pattern.lower() in title.lower() for pattern in deny):
                    continue
                fingerprint = stable_hash({"url": full_url, "title": title})
                if fingerprint in seen:
                    continue
                seen.add(fingerprint)
                items.append({"doc_id": fingerprint, "title": title[:220], "url": full_url})
        return items[: payload.metadata.get("max_links", 25)]

    def normalize(self, parsed: list[dict[str, Any]], payload: RawPayload) -> list[DocumentRecord]:
        documents: list[DocumentRecord] = []
        default_tags = payload.metadata.get("tags", [])
        for row in parsed:
            documents.append(
                DocumentRecord(
                    source_id=self.manifest.source_id,
                    doc_id=row["doc_id"],
                    title=row["title"],
                    summary=row.get("summary") or f"Discovered from {self.manifest.name}",
                    url=row.get("url"),
                    content_type="text/html",
                    published_at=parse_datetime(row.get("published_at")),
                    ingested_at=payload.retrieved_at,
                    tags=list(default_tags),
                    metadata=row,
                    provenance=Provenance(
                        source_id=self.manifest.source_id,
                        source_url=row.get("url"),
                        source_published_at=parse_datetime(row.get("published_at")),
                        ingested_at=payload.retrieved_at,
                    ),
                )
            )
        return documents
