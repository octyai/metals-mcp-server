
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class SourceManifest(BaseModel):
    source_id: str
    name: str
    adapter_type: str
    description: str
    category: Literal["market", "fundamentals", "weather", "events", "regulatory", "documents"]
    enabled: bool = True
    cadence_class: str = "daily"
    access_method: str = "http"
    base_url: str | None = None
    auth: str = "none"
    freshness_sla_seconds: int = 3600
    criticality: str = "tier_b"
    settings: dict[str, Any] = Field(default_factory=dict)


class SourceArtifact(BaseModel):
    source_id: str
    artifact_id: str
    kind: str
    url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RawPayload(BaseModel):
    source_id: str
    artifact_id: str
    retrieved_at: datetime
    content_type: str = "application/json"
    text: str | None = None
    data: dict[str, Any] | list[Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Provenance(BaseModel):
    source_id: str
    source_url: str | None = None
    source_published_at: datetime | None = None
    ingested_at: datetime
    raw_pointer: str | None = None
    retrieval_hash: str | None = None


class ValidationIssue(BaseModel):
    level: Literal["warning", "error"]
    message: str
    field: str | None = None


class ValidationResult(BaseModel):
    ok: bool = True
    issues: list[ValidationIssue] = Field(default_factory=list)
