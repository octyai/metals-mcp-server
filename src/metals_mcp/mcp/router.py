from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from metals_mcp.exceptions import AuthorizationError, NotFoundError
from metals_mcp.models.mcp import JsonRpcError, JsonRpcRequest, JsonRpcResponse
from metals_mcp.models.tools import (
    GenerateReportRequest,
    GetAssetStatusRequest,
    GetMarketSnapshotRequest,
    IngestSourceRequest,
    QuerySeriesRequest,
    RunScenarioRequest,
    SearchMetalsEventsRequest,
)
from metals_mcp.mcp.session import SessionHub
from metals_mcp.mcp.tools import tool_catalog
from metals_mcp.service import MetalsMCPService


class McpRouter:
    def __init__(self, service: MetalsMCPService, session_hub: SessionHub, settings) -> None:
        self.service = service
        self.session_hub = session_hub
        self.settings = settings
        self.router = APIRouter()
        self.router.add_api_route("/mcp", self.handle_post, methods=["POST"], response_model=None)
        self.router.add_api_route("/mcp", self.handle_stream, methods=["GET"], response_model=None)
        self.router.add_api_route("/.well-known/oauth-protected-resource", self.oauth_resource_metadata, methods=["GET"])

    def _validate_auth(self, authorization: str | None) -> None:
        if not self.settings.auth_tokens:
            return
        if not authorization or not authorization.startswith("Bearer "):
            raise AuthorizationError("Missing bearer token")
        token = authorization.split(" ", 1)[1].strip()
        if token not in self.settings.auth_tokens:
            raise AuthorizationError("Invalid bearer token")

    def _validate_origin(self, origin: str | None) -> None:
        if not origin or not self.settings.allowed_origins:
            return
        if origin not in self.settings.allowed_origins:
            raise AuthorizationError(f"Origin not allowed: {origin}")

    async def oauth_resource_metadata(self) -> dict[str, Any]:
        return {
            "resource": "/mcp",
            "authorization_servers": self.settings.authorization_servers or [],
            "scopes_supported": ["metals.read", "metals.ingest", "metals.report"],
            "bearer_methods_supported": ["header"],
        }

    async def handle_stream(
        self,
        request: Request,
        authorization: str | None = Header(default=None),
        origin: str | None = Header(default=None),
        session_id: str | None = None,
    ) -> StreamingResponse:
        try:
            self._validate_auth(authorization)
            self._validate_origin(origin)
        except AuthorizationError as exc:
            headers = {"WWW-Authenticate": 'Bearer resource_metadata="/.well-known/oauth-protected-resource"'}
            raise HTTPException(status_code=401, detail=str(exc), headers=headers) from exc
        sid = session_id or str(uuid4())
        queue = self.session_hub.queue_for(sid)

        async def event_stream():
            yield f"event: session\ndata: {sid}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=10.0)
                    yield f"data: {message}\n\n"
                except asyncio.TimeoutError:
                    yield "event: ping\ndata: {}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"X-MCP-Session-ID": sid})

    async def handle_post(
        self,
        request: Request,
        response: Response,
        authorization: str | None = Header(default=None),
        origin: str | None = Header(default=None),
        x_mcp_session_id: str | None = Header(default=None),
    ) -> Response | JsonRpcResponse:
        try:
            self._validate_auth(authorization)
            self._validate_origin(origin)
        except AuthorizationError as exc:
            headers = {"WWW-Authenticate": 'Bearer resource_metadata="/.well-known/oauth-protected-resource"'}
            raise HTTPException(status_code=401, detail=str(exc), headers=headers) from exc
        body = await request.json()
        rpc = JsonRpcRequest.model_validate(body)
        session_id = x_mcp_session_id
        try:
            result = await self.dispatch(rpc, session_id=session_id)
            if rpc.id is None:
                return Response(status_code=202)
            response.headers["X-MCP-Session-ID"] = session_id or ""
            return JsonRpcResponse(id=rpc.id, result=result)
        except Exception as exc:
            if rpc.id is None:
                return Response(status_code=500)
            return JsonRpcResponse(id=rpc.id, error=JsonRpcError(code=-32000, message=str(exc)))

    async def dispatch(self, rpc: JsonRpcRequest, session_id: str | None = None) -> dict[str, Any]:
        method = rpc.method
        params = rpc.params or {}
        if method == "initialize":
            return {
                "protocolVersion": "2025-11-25",
                "serverInfo": {"name": "metals-mcp-server", "version": "0.1.0"},
                "capabilities": {
                    "resources": {"listChanged": False},
                    "tools": {"listChanged": False},
                    "prompts": {"listChanged": False},
                },
            }
        if method == "notifications/initialized":
            return {}
        if method == "ping":
            return {"ok": True}
        if method == "resources/list":
            return {"resources": [resource.model_dump(mode="json") for resource in self.service.list_resources()]}
        if method == "resources/read":
            uri = params["uri"]
            data = self.service.read_resource(uri)
            return {"contents": [{"uri": uri, "mimeType": "application/json", "text": __import__("json").dumps(data, indent=2, default=str)}]}
        if method == "prompts/list":
            return {"prompts": [prompt.model_dump(mode="json") for prompt in self.service.list_prompts()]}
        if method == "prompts/get":
            return self.service.get_prompt(params["name"], params.get("arguments"))
        if method == "tools/list":
            return {
                "tools": [
                    {
                        "name": tool.name,
                        "title": tool.title,
                        "description": tool.description,
                        "inputSchema": tool.input_schema,
                    }
                    for tool in tool_catalog()
                ]
            }
        if method == "tools/call":
            return await self.call_tool(params.get("name"), params.get("arguments") or {}, session_id=session_id)
        raise NotFoundError(f"Unsupported method: {method}")

    async def call_tool(self, name: str, arguments: dict[str, Any], session_id: str | None = None) -> dict[str, Any]:
        if session_id:
            await self.session_hub.emit(session_id, {"jsonrpc": "2.0", "method": "notifications/progress", "params": {"progress": 0.1, "message": f"Starting {name}"}})
        if name == "query_series":
            structured = self.service.query_series(QuerySeriesRequest.model_validate(arguments))
        elif name == "get_market_snapshot":
            structured = self.service.get_market_snapshot(GetMarketSnapshotRequest.model_validate(arguments))
        elif name == "search_metals_events":
            structured = self.service.search_events(SearchMetalsEventsRequest.model_validate(arguments))
        elif name == "generate_report":
            if session_id:
                await self.session_hub.emit(session_id, {"jsonrpc": "2.0", "method": "notifications/progress", "params": {"progress": 0.4, "message": "Building evidence bundle"}})
            structured = self.service.generate_report(GenerateReportRequest.model_validate(arguments))
        elif name == "run_scenario":
            structured = self.service.run_scenario(RunScenarioRequest.model_validate(arguments))
        elif name == "get_asset_status":
            structured = self.service.get_asset_status(GetAssetStatusRequest.model_validate(arguments))
        elif name == "ingest_source":
            payload = IngestSourceRequest.model_validate(arguments)
            structured = {"summaries": self.service.ingest_sources(source_id=payload.source_id, all_sources=payload.all_sources)}
        else:
            raise NotFoundError(f"Unknown tool: {name}")
        if session_id:
            await self.session_hub.emit(session_id, {"jsonrpc": "2.0", "method": "notifications/progress", "params": {"progress": 1.0, "message": f"Completed {name}"}})
        text = structured.get("markdown") if isinstance(structured, dict) and "markdown" in structured else __import__("json").dumps(structured, indent=2, default=str)
        return {
            "content": [{"type": "text", "text": text}],
            "structuredContent": structured,
            "isError": False,
        }
