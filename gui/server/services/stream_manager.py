import asyncio
import base64
import gzip
from typing import List
from fastapi import WebSocket

class StreamManager:
    _instance = None
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.frame_connections: List[WebSocket] = []  # Separate list for frame streaming
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
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.frame_connections:
            self.frame_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # Handle disconnected clients gracefully
                pass

    async def connect_frame_stream(self, websocket: WebSocket):
        """Connect a WebSocket for frame streaming."""
        if self.main_loop is None:
            try:
                self.main_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass
        await websocket.accept()
        self.frame_connections.append(websocket)

    def disconnect_frame_stream(self, websocket: WebSocket):
        """Disconnect a frame streaming WebSocket."""
        if websocket in self.frame_connections:
            self.frame_connections.remove(websocket)

    async def broadcast_frame(self, frame_bytes: bytes, timestamp: float):
        """Broadcast frame data to all connected frame stream clients."""
        if not self.frame_connections:
            return
        
        # Compress frame data with gzip to reduce transmission size
        try:
            compressed_frame = gzip.compress(frame_bytes, compresslevel=6)  # Level 6 is a good balance
            # Only use compression if it actually reduces size (at least 10% reduction)
            if len(compressed_frame) < len(frame_bytes) * 0.9:
                frame_b64 = base64.b64encode(compressed_frame).decode('utf-8')
                compressed = True
            else:
                # Compression didn't help, use original
                frame_b64 = base64.b64encode(frame_bytes).decode('utf-8')
                compressed = False
        except Exception:
            # If compression fails, use original uncompressed data
            frame_b64 = base64.b64encode(frame_bytes).decode('utf-8')
            compressed = False
        
        message = {
            "type": "frame",
            "data": frame_b64,
            "compressed": compressed,  # Flag to indicate if data is compressed
            "timestamp": int(timestamp * 1000)  # Convert to milliseconds
        }
        
        # Send to all frame connections
        disconnected = []
        for connection in self.frame_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # Mark for removal
                disconnected.append(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect_frame_stream(conn)

stream_manager = StreamManager.get_instance()
