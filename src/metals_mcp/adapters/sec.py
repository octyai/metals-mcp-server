
from __future__ import annotations

from typing import Any

from metals_mcp.adapters.base import SourceAdapter
from metals_mcp.models.canonical import DocumentRecord
from metals_mcp.models.common import Provenance, RawPayload, SourceArtifact
from metals_mcp.utils import now_utc, parse_datetime, stable_hash


class SECSubmissionsAdapter(SourceAdapter):
    def discover(self) -> list[SourceArtifact]:
        companies = self.manifest.settings.get("companies", [])
        if self.use_fixtures():
            companies = self.load_fixture_json("discover.json")
        artifacts: list[SourceArtifact] = []
        for item in companies:
            cik = str(item["cik"]).zfill(10)
            url = item.get("url") or f"https://data.sec.gov/submissions/CIK{cik}.json"
            artifacts.append(SourceArtifact(source_id=self.manifest.source_id, artifact_id=item.get("artifact_id", cik), kind="json", url=url, metadata=item))
        return artifacts

    def fetch(self, artifact: SourceArtifact) -> RawPayload:
        if self.use_fixtures():
            data = self.load_fixture_json(f"{artifact.artifact_id}.json")
            return RawPayload(source_id=self.manifest.source_id, artifact_id=artifact.artifact_id, retrieved_at=now_utc(), data=data, metadata=artifact.metadata)
        response = self._http.get(artifact.url)
        response.raise_for_status()
        return RawPayload(source_id=self.manifest.source_id, artifact_id=artifact.artifact_id, retrieved_at=now_utc(), data=response.json(), metadata=artifact.metadata)

    def parse(self, payload: RawPayload) -> list[dict[str, Any]]:
        data = payload.data or {}
        recent = (data.get("filings") or {}).get("recent") or {}
        forms = recent.get("form", [])
        rows: list[dict[str, Any]] = []
        for idx, form in enumerate(forms[:25]):
            rows.append(
                {
                    "form": form,
                    "filingDate": recent.get("filingDate", [None])[idx],
                    "primaryDocument": recent.get("primaryDocument", [None])[idx],
                    "accessionNumber": recent.get("accessionNumber", [None])[idx],
                    "companyName": data.get("name"),
                    "cik": data.get("cik"),
                    "ticker": (data.get("tickers") or [None])[0],
                }
            )
        return rows

    def normalize(self, parsed: list[dict[str, Any]], payload: RawPayload) -> list[DocumentRecord]:
        documents: list[DocumentRecord] = []
        for row in parsed:
            accession = row.get("accessionNumber")
            if not accession:
                continue
            accession_nodash = accession.replace("-", "")
            cik = str(row.get("cik") or payload.metadata.get("cik") or "").lstrip("0")
            primary_document = row.get("primaryDocument")
            url = None
            if cik and primary_document:
                url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{primary_document}"
            published = parse_datetime(row.get("filingDate"))
            documents.append(
                DocumentRecord(
                    source_id=self.manifest.source_id,
                    doc_id=accession,
                    title=f"{row.get('companyName')} {row.get('form')} filing",
                    summary=f"{row.get('companyName')} filed {row.get('form')} ({row.get('ticker')})",
                    url=url,
                    content_type="application/json",
                    published_at=published,
                    ingested_at=payload.retrieved_at,
                    tags=[tag for tag in [row.get("ticker"), row.get("form"), "sec"] if tag],
                    metadata=row,
                    provenance=Provenance(
                        source_id=self.manifest.source_id,
                        source_url=payload.metadata.get("url") or url,
                        source_published_at=published,
                        ingested_at=payload.retrieved_at,
                    ),
                )
            )
        return documents
