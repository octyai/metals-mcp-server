from __future__ import annotations


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
