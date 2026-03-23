
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field

from metals_mcp.config import Settings
from metals_mcp.models.canonical import DocumentRecord, EventRecord, ObservationRecord
from metals_mcp.models.common import RawPayload, SourceArtifact, SourceManifest, ValidationResult
from metals_mcp.storage.raw_archive import RawArchiveStore
from metals_mcp.storage.sqlite_store import SqliteStore
from metals_mcp.utils import load_json, load_text, now_utc


class IngestSummary(BaseModel):
    source_id: str
    artifacts_seen: int = 0
    observations_saved: int = 0
    events_saved: int = 0
    documents_saved: int = 0
    warnings: list[str] = Field(default_factory=list)


class SourceAdapter(ABC):
    def __init__(self, manifest: SourceManifest, settings: Settings) -> None:
        self.manifest = manifest
        self.settings = settings
        self.logger = logging.getLogger(f"metals_mcp.adapters.{manifest.source_id}")
        self._http = httpx.Client(
            timeout=settings.http_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": settings.user_agent},
        )

    @property
    def fixture_root(self) -> Path:
        return Path(__file__).resolve().parent.parent / "fixtures" / self.manifest.source_id

    def close(self) -> None:
        self._http.close()

    def use_fixtures(self) -> bool:
        return self.settings.mode == "fixture"

    def load_fixture_json(self, name: str) -> Any:
        return load_json(self.fixture_root / name)

    def load_fixture_text(self, name: str) -> str:
        return load_text(self.fixture_root / name)

    @abstractmethod
    def discover(self) -> list[SourceArtifact]:
        raise NotImplementedError

    @abstractmethod
    def fetch(self, artifact: SourceArtifact) -> RawPayload:
        raise NotImplementedError

    @abstractmethod
    def parse(self, payload: RawPayload) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def normalize(self, parsed: list[dict[str, Any]], payload: RawPayload) -> list[ObservationRecord | EventRecord | DocumentRecord]:
        raise NotImplementedError

    def validate(self, records: list[ObservationRecord | EventRecord | DocumentRecord]) -> ValidationResult:
        return ValidationResult(ok=True, issues=[])

    def ingest_once(self, store: SqliteStore, archive: RawArchiveStore) -> IngestSummary:
        summary = IngestSummary(source_id=self.manifest.source_id)
        store.upsert_source(self.manifest)
        for artifact in self.discover():
            summary.artifacts_seen += 1
            payload = self.fetch(artifact)
            archive_path = archive.save(self.manifest.source_id, artifact.artifact_id, payload.data or payload.text or "", suffix=".json" if payload.data is not None else ".txt")
            payload.metadata["raw_pointer"] = archive_path
            parsed = self.parse(payload)
            records = self.normalize(parsed, payload)
            validation = self.validate(records)
            for issue in validation.issues:
                summary.warnings.append(issue.message)
            for record in records:
                if hasattr(record, "provenance") and record.provenance.raw_pointer is None:
                    record.provenance.raw_pointer = archive_path
                if isinstance(record, ObservationRecord):
                    store.save_observation(record)
                    summary.observations_saved += 1
                elif isinstance(record, EventRecord):
                    store.save_event(record)
                    summary.events_saved += 1
                elif isinstance(record, DocumentRecord):
                    store.save_document(record)
                    summary.documents_saved += 1
        return summary
