from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from metals_mcp.app import create_app


@pytest.fixture()
def auth_app_env(tmp_path, monkeypatch):
    """App environment with auth tokens configured."""
    monkeypatch.setenv("METALS_MCP_MODE", "fixture")
    monkeypatch.setenv("METALS_MCP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("METALS_MCP_DB_PATH", str(tmp_path / "metals_mcp.db"))
    monkeypatch.setenv("METALS_MCP_AUTH_TOKENS", "test-secret-token")
    return tmp_path


@pytest.fixture()
def auth_client(auth_app_env):
    app = create_app()
    with TestClient(app) as client:
        yield client


def test_auth_missing_token_returns_401(auth_client):
    """When METALS_MCP_AUTH_TOKENS is set, requests without a Bearer token return 401."""
    response = auth_client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"


def test_auth_invalid_token_returns_401(auth_client):
    """When METALS_MCP_AUTH_TOKENS is set, requests with an invalid Bearer token return 401."""
    response = auth_client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"


def test_mcp_initialize(client):
    response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    payload = response.json()
    assert payload["result"]["protocolVersion"] == "2025-11-25"


def test_mcp_tool_call(client, app):
    app.state.service.ingest_sources(all_sources=True)
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "get_market_snapshot",
                "arguments": {"scope": "global", "include": ["prices", "news"]},
            },
        },
    )
    payload = response.json()
    assert payload["result"]["structuredContent"]["series"]


def test_mcp_resources(client, app):
    app.state.service.ingest_sources(all_sources=True)
    response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 3, "method": "resources/read", "params": {"uri": "metals://events/active"}})
    payload = response.json()
    assert payload["result"]["contents"][0]["uri"] == "metals://events/active"
