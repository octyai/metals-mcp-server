
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl

from metals_mcp.models.common import Provenance


class ObservationRecord(BaseModel):
    record_type: Literal["observation"] = "observation"
    source_id: str
    series_id: str
    label: str | None = None
    observed_at: datetime
    published_at: datetime | None = None
    ingested_at: datetime
    value: float
    unit: str
    geo: str | None = None
    commodity: str | None = None
    frequency: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance


class EventRecord(BaseModel):
    record_type: Literal["event"] = "event"
    source_id: str
    event_id: str
    title: str
    summary: str | None = None
    event_type: str = "news"
    severity: Literal["low", "medium", "high"] = "medium"
    geo: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    ingested_at: datetime
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance


class DocumentRecord(BaseModel):
    record_type: Literal["document"] = "document"
    source_id: str
    doc_id: str
    title: str
    summary: str | None = None
    url: str | None = None
    content_type: str = "text/html"
    published_at: datetime | None = None
    ingested_at: datetime
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance


class ReportArtifact(BaseModel):
    report_id: str
    template_name: str
    created_at: datetime
    scope: str
    payload: dict[str, Any]
    markdown: str
    citations: list[str] = Field(default_factory=list)
