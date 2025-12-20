from fastapi import APIRouter
from pydantic import BaseModel
import os
from phone_agent.config.apps import list_supported_apps

router = APIRouter()

class HealthResponse(BaseModel):
    status: str
    version: str

@router.get("/health", response_model=HealthResponse)
async def health_check():
    return {"status": "ok", "version": "1.0.0"}

@router.get("/apps")
async def get_supported_apps():
    return {"apps": list_supported_apps()}
