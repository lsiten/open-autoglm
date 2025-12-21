from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List
from ..services.agent_runner import agent_runner
from ..services.stream_manager import stream_manager
from ..services.config_manager import config_manager

router = APIRouter()

class ChatRequest(BaseModel):
    prompt: str

class ConfigRequest(BaseModel):
    base_url: str
    model: str
    api_key: str

class AppMatchingConfigRequest(BaseModel):
    system_app_mappings: Optional[Dict[str, List[str]]] = None
    llm_prompt_template: Optional[str] = None

class SystemPromptRequest(BaseModel):
    prompt: str
    lang: str = "cn"

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

@router.get("/app-matching-config")
async def get_app_matching_config():
    """Get app matching configuration."""
    return {
        "system_app_mappings": config_manager.get_system_app_mappings(),
        "llm_prompt_template": config_manager.get_llm_prompt_template()
    }

@router.post("/app-matching-config")
async def update_app_matching_config(req: AppMatchingConfigRequest):
    """Update app matching configuration."""
    config_manager.update_config(
        system_app_mappings=req.system_app_mappings,
        llm_prompt_template=req.llm_prompt_template
    )
    return {"status": "updated", "config": config_manager.get_all_config()}

@router.get("/system-prompt")
async def get_system_prompt(lang: str = "cn"):
    """Get system prompt configuration."""
    # Get raw prompt (for editing, with {date} placeholder)
    prompt, is_custom = config_manager.get_system_prompt_raw(lang)
    return {
        "prompt": prompt,
        "is_custom": is_custom,
        "lang": lang
    }

@router.post("/system-prompt")
async def update_system_prompt(req: SystemPromptRequest):
    """Update system prompt configuration."""
    config_manager.update_system_prompt(req.prompt, req.lang)
    return {"status": "updated"}

@router.post("/system-prompt/reset")
async def reset_system_prompt(lang: str = "cn"):
    """Reset system prompt to default."""
    config_manager.reset_system_prompt(lang)
    return {"status": "reset"}

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
