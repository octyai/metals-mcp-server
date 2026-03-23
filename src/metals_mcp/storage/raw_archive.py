
from __future__ import annotations

from pathlib import Path
from typing import Any

from metals_mcp.utils import json_dumps, stable_hash


class RawArchiveStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, source_id: str, artifact_id: str, payload: Any, suffix: str = ".json") -> str:
        fingerprint = stable_hash(payload)
        target = self.root / source_id / artifact_id
        target.mkdir(parents=True, exist_ok=True)
        path = target / f"{fingerprint}{suffix}"
        if isinstance(payload, bytes):
            path.write_bytes(payload)
        elif isinstance(payload, str):
            path.write_text(payload, encoding="utf-8")
        else:
            path.write_text(json_dumps(payload), encoding="utf-8")
        return str(path)
