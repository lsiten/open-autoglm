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
    device_id: Optional[str] = None

class SystemPromptOptimizeRequest(BaseModel):
    current_prompt: str
    user_request: str
    lang: str = "cn"
    device_id: Optional[str] = None

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
async def get_system_prompt(lang: str = "cn", device_id: Optional[str] = None):
    """Get system prompt configuration.
    
    If device_id is provided, returns device-specific prompt if exists, otherwise global prompt.
    """
    # Get raw prompt (for editing, with {date} placeholder)
    prompt, is_custom = config_manager.get_system_prompt_raw(lang, device_id=device_id)
    return {
        "prompt": prompt,
        "is_custom": is_custom,
        "lang": lang,
        "device_id": device_id
    }

@router.post("/system-prompt")
async def update_system_prompt(req: SystemPromptRequest):
    """Update system prompt configuration.
    
    If device_id is provided in request, updates device-specific prompt; otherwise updates global prompt.
    """
    if hasattr(req, 'device_id') and req.device_id:
        config_manager.update_device_system_prompt(req.device_id, req.prompt, req.lang)
    else:
        config_manager.update_system_prompt(req.prompt, req.lang)
    return {"status": "updated"}

@router.post("/system-prompt/reset")
async def reset_system_prompt(lang: str = "cn", device_id: Optional[str] = None):
    """Reset system prompt to default.
    
    If device_id is provided, resets device-specific prompt; otherwise resets global prompt.
    """
    config_manager.reset_system_prompt(lang, device_id=device_id)
    return {"status": "reset"}

@router.post("/system-prompt/optimize")
async def optimize_system_prompt(req: SystemPromptOptimizeRequest):
    """Optimize system prompt based on user request.
    
    Uses the configured model to analyze the current prompt and optimize it
    according to the user's requirements while maintaining existing rules.
    """
    try:
        from phone_agent.model import ModelClient, ModelConfig
        from phone_agent.model.client import MessageBuilder
        
        # Get model config from agent_runner
        api_key = agent_runner.api_key if agent_runner.api_key != "EMPTY" else ""
        model_config = ModelConfig(
            base_url=agent_runner.base_url,
            model_name=agent_runner.model_name,
            api_key=api_key,
            lang=req.lang,
            max_tokens=4000,  # Allow more tokens for optimization
            temperature=0.3  # Slightly higher temperature for creative optimization
        )
        
        model_client = ModelClient(model_config)
        
        # Build optimization prompt
        if req.lang == "cn":
            system_message = """你是一个专业的提示词优化助手。你的任务是帮助用户优化系统提示词，使其更符合用户的需求，同时保持原有的规则和结构。

重要原则：
1. 仔细分析当前提示词的所有规则和要求
2. 理解用户的需求和优化方向
3. 在保持原有规则完整性的基础上进行优化
4. 确保优化后的提示词更加清晰、准确、有效
5. 不要删除或忽略原有的重要规则
6. 如果用户需求与现有规则冲突，优先保持规则完整性，但可以添加说明或补充

请直接返回优化后的完整提示词，不要添加任何解释或说明文字。"""
            
            user_message = f"""当前系统提示词：

{req.current_prompt}

用户优化需求：
{req.user_request}

请基于以上信息，优化系统提示词。要求：
1. 保持所有原有规则和结构
2. 根据用户需求进行针对性优化
3. 确保优化后的提示词更加清晰有效
4. 直接返回优化后的完整提示词，不要添加任何解释"""
        else:
            system_message = """You are a professional prompt optimization assistant. Your task is to help users optimize system prompts to better meet their needs while maintaining existing rules and structure.

Key principles:
1. Carefully analyze all rules and requirements in the current prompt
2. Understand the user's needs and optimization direction
3. Optimize while maintaining the integrity of existing rules
4. Ensure the optimized prompt is clearer, more accurate, and more effective
5. Do not delete or ignore important existing rules
6. If user needs conflict with existing rules, prioritize rule integrity but can add explanations or supplements

Please directly return the optimized complete prompt without any explanations or additional text."""
            
            user_message = f"""Current system prompt:

{req.current_prompt}

User optimization request:
{req.user_request}

Please optimize the system prompt based on the above information. Requirements:
1. Maintain all existing rules and structure
2. Optimize according to user needs
3. Ensure the optimized prompt is clearer and more effective
4. Directly return the optimized complete prompt without any explanations"""
        
        messages = [
            MessageBuilder.create_system_message(system_message),
            MessageBuilder.create_user_message(user_message)
        ]
        
        # Call model to optimize
        response = model_client.request(messages)
        
        # Extract optimized prompt from response
        # Priority: raw_content > thinking > action
        optimized_prompt = ""
        
        # First try raw_content (most complete)
        if response.raw_content and len(response.raw_content.strip()) > 50:
            optimized_prompt = response.raw_content.strip()
        # Then try thinking
        elif response.thinking and len(response.thinking.strip()) > 50:
            optimized_prompt = response.thinking.strip()
        # Finally try action
        elif response.action:
            optimized_prompt = response.action.strip()
        
        # Clean up the prompt (remove any action markers or extra formatting)
        if optimized_prompt:
            import re
            # Remove action markers like finish(message="...") or do(action="...")
            # Try to extract content from finish(message="...")
            finish_match = re.search(r'finish\(message=["\'](.*?)["\']\)', optimized_prompt, re.DOTALL)
            if finish_match:
                optimized_prompt = finish_match.group(1)
            else:
                # Remove common action markers
                optimized_prompt = re.sub(r'finish\(message=["\']?', '', optimized_prompt)
                optimized_prompt = re.sub(r'do\(action=["\']?', '', optimized_prompt)
                optimized_prompt = optimized_prompt.rstrip(')"').strip()
            
            # Remove XML tags if present
            optimized_prompt = re.sub(r'<answer>|</answer>', '', optimized_prompt).strip()
            optimized_prompt = re.sub(r'<think>.*?</think>', '', optimized_prompt, flags=re.DOTALL).strip()
        
        if not optimized_prompt or len(optimized_prompt) < 50:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate optimized prompt. The model response was too short or invalid."
            )
        
        return {
            "status": "success",
            "optimized_prompt": optimized_prompt
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to optimize prompt: {str(e)}"
        )

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
