from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(slots=True)
class Settings:
    env: str = "development"
    mode: str = "fixture"
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    data_dir: Path = Path("./data")
    db_path: Path = Path("./data/metals_mcp.db")
    raw_dir: Path = Path("./data/raw")
    reports_dir: Path = Path("./data/reports")
    allowed_origins: list[str] = field(default_factory=list)
    auth_tokens: list[str] = field(default_factory=list)
    authorization_servers: list[str] = field(default_factory=list)
    http_timeout_seconds: float = 20.0
    user_agent: str = "metals-mcp-server/0.1 (+contact@example.com)"
    fred_api_key: str | None = None
    enable_metrics: bool = True
    tracked_regions: list[str] = field(
        default_factory=lambda: [
            "North America",
            "Latin America",
            "South Africa",
            "Indonesia",
            "Australia",
            "London",
        ]
    )

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(os.getenv("METALS_MCP_DATA_DIR", "./data"))
        db_path = Path(os.getenv("METALS_MCP_DB_PATH", str(data_dir / "metals_mcp.db")))
        settings = cls(
            env=os.getenv("METALS_MCP_ENV", "development"),
            mode=os.getenv("METALS_MCP_MODE", "fixture"),
            host=os.getenv("METALS_MCP_HOST", "0.0.0.0"),
            port=int(os.getenv("METALS_MCP_PORT", "8080")),
            debug=os.getenv("METALS_MCP_DEBUG", "false").lower() in {"1", "true", "yes"},
            data_dir=data_dir,
            db_path=db_path,
            raw_dir=Path(os.getenv("METALS_MCP_RAW_DIR", str(data_dir / "raw"))),
            reports_dir=Path(os.getenv("METALS_MCP_REPORTS_DIR", str(data_dir / "reports"))),
            allowed_origins=_split_csv(os.getenv("METALS_MCP_ALLOWED_ORIGINS")),
            auth_tokens=_split_csv(os.getenv("METALS_MCP_AUTH_TOKENS")),
            authorization_servers=_split_csv(os.getenv("METALS_MCP_AUTHORIZATION_SERVERS")),
            http_timeout_seconds=float(os.getenv("METALS_MCP_HTTP_TIMEOUT_SECONDS", "20")),
            user_agent=os.getenv("METALS_MCP_USER_AGENT", "metals-mcp-server/0.1 (+contact@example.com)"),
            fred_api_key=os.getenv("METALS_MCP_FRED_API_KEY"),
            enable_metrics=os.getenv("METALS_MCP_ENABLE_METRICS", "true").lower() in {"1", "true", "yes"},
            tracked_regions=_split_csv(
                os.getenv(
                    "METALS_MCP_TRACKED_REGIONS",
                    "North America,Latin America,South Africa,Indonesia,Australia,London",
                )
            ),
        )
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        settings.raw_dir.mkdir(parents=True, exist_ok=True)
        settings.reports_dir.mkdir(parents=True, exist_ok=True)
        return settings
