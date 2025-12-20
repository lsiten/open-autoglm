from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from gui.server.services.task_manager import task_manager, AgentTask
from gui.server.services.agent_runner import agent_runner

router = APIRouter()

class CreateTaskRequest(BaseModel):
    id: Optional[str] = None # Allow explicit ID (for session sync)
    device_id: str
    type: str # 'chat' or 'background'
    name: str
    role: Optional[str] = None
    details: Optional[str] = None

class TaskResponse(BaseModel):
    task: AgentTask

@router.get("/{device_id}", response_model=List[AgentTask])
async def list_device_tasks(device_id: str):
    return task_manager.list_tasks(device_id)

@router.post("/", response_model=TaskResponse)
async def create_task(req: CreateTaskRequest):
    task = task_manager.create_task(
        id=req.id,
        device_id=req.device_id,
        type=req.type,
        name=req.name,
        role=req.role,
        details=req.details
    )
    return {"task": task}

@router.get("/detail/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": task}

class UpdateTaskRequest(BaseModel):
    name: Optional[str] = None
    details: Optional[str] = None

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: str, req: UpdateTaskRequest):
    task = task_manager.update_task(task_id, name=req.name, details=req.details)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": task}

class StartTaskRequest(BaseModel):
    prompt: Optional[str] = None
    installed_apps: Optional[List[Dict[str, str]]] = None

@router.post("/{task_id}/start")
async def start_task(task_id: str, req: StartTaskRequest = None):
    prompt = req.prompt if req else None
    installed_apps = req.installed_apps if req else None
    success, msg = agent_runner.start_session(task_id, prompt, installed_apps)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "started", "message": msg}

class InteractionRequest(BaseModel):
    response: Any

@router.post("/{task_id}/interaction")
async def handle_interaction(task_id: str, req: InteractionRequest):
    success = agent_runner.handle_interaction_response(task_id, req.response)
    if not success:
        # It might be that no interaction is pending, or task not found
        # But for UI UX, just returning ok is fine, or 400 if strictly needed.
        # Let's return 200 with status info
        return {"status": "ignored", "message": "No pending interaction found"}
    return {"status": "processed"}

@router.post("/{task_id}/stop")
async def stop_task(task_id: str):
    success = agent_runner.stop_task(task_id)
    if not success:
         # Maybe it wasn't running, but we mark it stopped anyway
         task_manager.update_status(task_id, "stopped")
    return {"status": "stopped"}

@router.delete("/{task_id}")
async def delete_task(task_id: str):
    agent_runner.stop_task(task_id) # Stop if running
    task_manager.delete_task(task_id)
    return {"status": "deleted"}
