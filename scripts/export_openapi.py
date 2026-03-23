from __future__ import annotations

import json
from pathlib import Path

from metals_mcp.app import create_app

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "schemas" / "openapi.json"
app = create_app()
OUT.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
print(f"wrote {OUT}")
