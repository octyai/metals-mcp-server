
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from metals_mcp.models.canonical import DocumentRecord, EventRecord, ObservationRecord, ReportArtifact
from metals_mcp.models.common import SourceManifest
from metals_mcp.utils import isoformat, json_dumps, parse_datetime


class SqliteStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def checkpoint(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS sources (
                    source_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT NOT NULL,
                    series_id TEXT NOT NULL,
                    label TEXT,
                    observed_at TEXT NOT NULL,
                    published_at TEXT,
                    ingested_at TEXT NOT NULL,
                    value REAL NOT NULL,
                    unit TEXT NOT NULL,
                    geo TEXT,
                    commodity TEXT,
                    frequency TEXT,
                    metadata_json TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    UNIQUE(source_id, series_id, observed_at)
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT NOT NULL,
                    event_id TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    summary TEXT,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    geo TEXT,
                    url TEXT,
                    published_at TEXT,
                    ingested_at TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    provenance_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT NOT NULL,
                    doc_id TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    summary TEXT,
                    url TEXT,
                    content_type TEXT NOT NULL,
                    published_at TEXT,
                    ingested_at TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    provenance_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_id TEXT NOT NULL UNIQUE,
                    template_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    markdown TEXT NOT NULL,
                    citations_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_observations_series_time ON observations(series_id, observed_at DESC);
                CREATE INDEX IF NOT EXISTS idx_events_time ON events(published_at DESC);
                CREATE INDEX IF NOT EXISTS idx_documents_time ON documents(published_at DESC);
                """
            )

    def upsert_source(self, manifest: SourceManifest) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sources(source_id, name, manifest_json, updated_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(source_id)
                DO UPDATE SET name=excluded.name, manifest_json=excluded.manifest_json, updated_at=excluded.updated_at
                """,
                (manifest.source_id, manifest.name, manifest.model_dump_json(), isoformat(datetime.now(tz=UTC))),
            )

    def list_sources(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM sources ORDER BY source_id").fetchall()
        return [dict(row) for row in rows]

    def save_observation(self, record: ObservationRecord) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO observations(
                    source_id, series_id, label, observed_at, published_at, ingested_at, value, unit,
                    geo, commodity, frequency, metadata_json, provenance_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.source_id,
                    record.series_id,
                    record.label,
                    isoformat(record.observed_at),
                    isoformat(record.published_at),
                    isoformat(record.ingested_at),
                    record.value,
                    record.unit,
                    record.geo,
                    record.commodity,
                    record.frequency,
                    json_dumps(record.metadata),
                    record.provenance.model_dump_json(),
                ),
            )

    def save_event(self, record: EventRecord) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO events(
                    source_id, event_id, title, summary, event_type, severity, geo, url,
                    published_at, ingested_at, tags_json, metadata_json, provenance_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.source_id,
                    record.event_id,
                    record.title,
                    record.summary,
                    record.event_type,
                    record.severity,
                    record.geo,
                    record.url,
                    isoformat(record.published_at),
                    isoformat(record.ingested_at),
                    json_dumps(record.tags),
                    json_dumps(record.metadata),
                    record.provenance.model_dump_json(),
                ),
            )

    def save_document(self, record: DocumentRecord) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO documents(
                    source_id, doc_id, title, summary, url, content_type,
                    published_at, ingested_at, tags_json, metadata_json, provenance_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.source_id,
                    record.doc_id,
                    record.title,
                    record.summary,
                    record.url,
                    record.content_type,
                    isoformat(record.published_at),
                    isoformat(record.ingested_at),
                    json_dumps(record.tags),
                    json_dumps(record.metadata),
                    record.provenance.model_dump_json(),
                ),
            )

    def save_report(self, artifact: ReportArtifact) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO reports(report_id, template_name, created_at, scope, payload_json, markdown, citations_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.report_id,
                    artifact.template_name,
                    isoformat(artifact.created_at),
                    artifact.scope,
                    json_dumps(artifact.payload),
                    artifact.markdown,
                    json_dumps(artifact.citations),
                ),
            )

    def latest_series_points(self, series_id: str, limit: int = 2) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM observations WHERE series_id = ? ORDER BY observed_at DESC LIMIT ?",
                (series_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def query_series(
        self,
        series_ids: list[str],
        start: datetime | None = None,
        end: datetime | None = None,
        geo: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        results: dict[str, list[dict[str, Any]]] = {series_id: [] for series_id in series_ids}
        if not series_ids:
            return results
        placeholders = ",".join("?" for _ in series_ids)
        clauses = [f"series_id IN ({placeholders})"]
        params: list[Any] = list(series_ids)
        if start:
            clauses.append("observed_at >= ?")
            params.append(isoformat(start))
        if end:
            clauses.append("observed_at <= ?")
            params.append(isoformat(end))
        if geo:
            clauses.append("geo = ?")
            params.append(geo)
        sql = f"SELECT * FROM observations WHERE {' AND '.join(clauses)} ORDER BY observed_at ASC"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        for row in rows:
            results[row['series_id']].append(dict(row))
        return results

    def latest_observations(self, limit_per_series: int = 1) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT o.* FROM observations o
                JOIN (
                    SELECT series_id, MAX(observed_at) AS max_observed_at
                    FROM observations
                    GROUP BY series_id
                ) latest
                ON o.series_id = latest.series_id AND o.observed_at = latest.max_observed_at
                ORDER BY o.series_id ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def recent_events(self, since_hours: int = 168, sources: list[str] | None = None) -> list[dict[str, Any]]:
        threshold = datetime.now(tz=UTC) - timedelta(hours=since_hours)
        params: list[Any] = [isoformat(threshold)]
        clauses = ["COALESCE(published_at, ingested_at) >= ?"]
        if sources:
            placeholders = ",".join("?" for _ in sources)
            clauses.append(f"source_id IN ({placeholders})")
            params.extend(sources)
        sql = f"SELECT * FROM events WHERE {' AND '.join(clauses)} ORDER BY COALESCE(published_at, ingested_at) DESC LIMIT 100"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def search_events(self, query: str, since_hours: int = 168, sources: list[str] | None = None) -> list[dict[str, Any]]:
        pattern = f"%{query.lower()}%"
        threshold = datetime.now(tz=UTC) - timedelta(hours=since_hours)
        clauses = ["(LOWER(title) LIKE ? OR LOWER(COALESCE(summary, '')) LIKE ?)", "COALESCE(published_at, ingested_at) >= ?"]
        params: list[Any] = [pattern, pattern, isoformat(threshold)]
        if sources:
            placeholders = ",".join("?" for _ in sources)
            clauses.append(f"source_id IN ({placeholders})")
            params.extend(sources)
        sql = f"SELECT * FROM events WHERE {' AND '.join(clauses)} ORDER BY COALESCE(published_at, ingested_at) DESC LIMIT 100"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def recent_documents(self, since_hours: int = 720, sources: list[str] | None = None) -> list[dict[str, Any]]:
        threshold = datetime.now(tz=UTC) - timedelta(hours=since_hours)
        clauses = ["COALESCE(published_at, ingested_at) >= ?"]
        params: list[Any] = [isoformat(threshold)]
        if sources:
            placeholders = ",".join("?" for _ in sources)
            clauses.append(f"source_id IN ({placeholders})")
            params.extend(sources)
        sql = f"SELECT * FROM documents WHERE {' AND '.join(clauses)} ORDER BY COALESCE(published_at, ingested_at) DESC LIMIT 100"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def source_status(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT s.source_id, s.name, s.updated_at,
                       (SELECT MAX(ingested_at) FROM observations WHERE source_id = s.source_id) AS latest_observation_ingest,
                       (SELECT MAX(ingested_at) FROM events WHERE source_id = s.source_id) AS latest_event_ingest,
                       (SELECT MAX(ingested_at) FROM documents WHERE source_id = s.source_id) AS latest_document_ingest,
                       (SELECT COUNT(*) FROM observations WHERE source_id = s.source_id) AS observation_count,
                       (SELECT COUNT(*) FROM events WHERE source_id = s.source_id) AS event_count,
                       (SELECT COUNT(*) FROM documents WHERE source_id = s.source_id) AS document_count
                FROM sources s ORDER BY s.source_id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_report(self, report_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM reports WHERE report_id = ?", (report_id,)).fetchone()
        return dict(row) if row else None

    def latest_reports(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM reports ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]
