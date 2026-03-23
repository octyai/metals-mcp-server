from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from metals_mcp.app import create_app


@pytest.fixture()
def app_env(tmp_path, monkeypatch):
    monkeypatch.setenv("METALS_MCP_MODE", "fixture")
    monkeypatch.setenv("METALS_MCP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("METALS_MCP_DB_PATH", str(tmp_path / "metals_mcp.db"))
    monkeypatch.setenv("METALS_MCP_AUTH_TOKENS", "")
    return tmp_path


@pytest.fixture()
def app(app_env):
    return create_app()


@pytest.fixture()
def client(app):
    with TestClient(app) as client:
        yield client
