from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from ..services.agent_runner import agent_runner
from ..services.stream_manager import stream_manager

router = APIRouter()

class ChatRequest(BaseModel):
    prompt: str

class ConfigRequest(BaseModel):
    base_url: str
    model: str
    api_key: str

@router.post("/chat")
async def chat(req: ChatRequest):
    success, msg = agent_runner.start_task(req.prompt)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "started", "message": msg}

@router.post("/stop")
async def stop_task():
    if agent_runner.stop_task():
        return {"status": "stopped"}
    return {"status": "not_running"}

@router.post("/config")
async def update_config(req: ConfigRequest):
    agent_runner.update_config(req.base_url, req.model, req.api_key)
    return {"status": "updated"}

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await stream_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, maybe handle client messages
            data = await websocket.receive_text()
            # Echo or process if needed
    except WebSocketDisconnect:
        stream_manager.disconnect(websocket)
