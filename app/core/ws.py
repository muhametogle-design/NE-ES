import asyncio
import json
import logging
from typing import Dict, Set, Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        # Maps school_id -> set of WebSockets; school_id=0 or None for state-wide channels
        self.active_connections: Dict[Optional[int], Set[WebSocket]] = {}
        self.state_connections: Set[WebSocket] = set()
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop

    async def connect(self, websocket: WebSocket, school_id: Optional[int] = None, is_state: bool = False):
        await websocket.accept()
        if is_state or school_id is None:
            self.state_connections.add(websocket)
        else:
            if school_id not in self.active_connections:
                self.active_connections[school_id] = set()
            self.active_connections[school_id].add(websocket)
        logger.info(f"WebSocket connected. school_id={school_id}, is_state={is_state}")

    def disconnect(self, websocket: WebSocket, school_id: Optional[int] = None):
        self.state_connections.discard(websocket)
        if school_id is not None and school_id in self.active_connections:
            self.active_connections[school_id].discard(websocket)
            if not self.active_connections[school_id]:
                del self.active_connections[school_id]
        logger.info(f"WebSocket disconnected. school_id={school_id}")

    async def broadcast_to_school(self, school_id: int, message: dict):
        # Send to school subscribers
        if school_id in self.active_connections:
            dead_connections = set()
            for connection in list(self.active_connections[school_id]):
                try:
                    await connection.send_json(message)
                except Exception:
                    dead_connections.add(connection)
            for dead in dead_connections:
                self.active_connections[school_id].discard(dead)

        # Also broadcast to state subscribers
        dead_state = set()
        for connection in list(self.state_connections):
            try:
                await connection.send_json(message)
            except Exception:
                dead_state.add(connection)
        for dead in dead_state:
            self.state_connections.discard(dead)

    async def broadcast_to_all(self, message: dict):
        for school_id in list(self.active_connections.keys()):
            await self.broadcast_to_school(school_id, message)
        for connection in list(self.state_connections):
            try:
                await connection.send_json(message)
            except Exception:
                pass

    def broadcast_sync(self, school_id: Optional[int], message: dict):
        if self.loop and self.loop.is_running():
            if school_id is not None:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast_to_school(school_id, message), self.loop
                )
            else:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast_to_all(message), self.loop
                )
        else:
            try:
                new_loop = asyncio.get_event_loop()
                if new_loop.is_running():
                    if school_id is not None:
                        new_loop.create_task(self.broadcast_to_school(school_id, message))
                    else:
                        new_loop.create_task(self.broadcast_to_all(message))
            except Exception as e:
                logger.warning(f"Could not broadcast sync message: {e}")

ws_manager = WebSocketManager()
