
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class JsonRpcRequest(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None = None
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


class JsonRpcError(BaseModel):
    code: int
    message: str
    data: Any | None = None


class JsonRpcResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None = None
    result: Any | None = None
    error: JsonRpcError | None = None


class McpResource(BaseModel):
    uri: str
    name: str
    description: str
    mimeType: str = "application/json"


class McpPrompt(BaseModel):
    name: str
    title: str
    description: str
    arguments: list[dict[str, Any]] = Field(default_factory=list)
