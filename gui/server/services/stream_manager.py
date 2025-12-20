import asyncio
from typing import List
from fastapi import WebSocket

class StreamManager:
    _instance = None
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.main_loop = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def connect(self, websocket: WebSocket):
        if self.main_loop is None:
            try:
                self.main_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # Handle disconnected clients gracefully
                pass

stream_manager = StreamManager.get_instance()
