from __future__ import annotations

import json
from pathlib import Path


def test_schema_files_exist_and_parse():
    root = Path(__file__).resolve().parents[1] / "schemas" / "generated"
    files = list(root.glob("*.json"))
    assert files
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload.get("type") == "object"
