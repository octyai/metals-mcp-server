
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from metals_mcp.utils import json_dumps


class SessionHub:
    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[str]] = defaultdict(asyncio.Queue)

    def queue_for(self, session_id: str) -> asyncio.Queue[str]:
        return self._queues[session_id]

    async def emit(self, session_id: str, payload: dict[str, Any]) -> None:
        await self.queue_for(session_id).put(json_dumps(payload))
