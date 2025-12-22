"""API routes for action recording management."""

import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from dataclasses import asdict
from ..services.recording_manager import recording_manager, Recording, RecordedAction
from ..services.device_manager import device_manager

# Thread pool for executing recording operations
_recording_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="recording-exec")
from ..services.recording_executor import _reset_to_home_first_page

router = APIRouter()

class StartRecordingRequest(BaseModel):
    device_id: str
    device_type: Optional[str] = "adb"

class SaveRecordingRequest(BaseModel):
    recording_id: str
    name: str
    keywords: List[str]
    description: Optional[str] = None

class ExecuteRecordingRequest(BaseModel):
    device_id: Optional[str] = None  # If not provided, use recording's device_id

class ExecuteSingleActionRequest(BaseModel):
    action_index: int
    device_id: Optional[str] = None

class ReplaceActionRequest(BaseModel):
    recording_id: str
    action_index: int
    new_action: dict  # RecordedAction as dict
    device_id: Optional[str] = None

@router.post("/start")
async def start_recording(req: StartRecordingRequest):
    """Start recording actions for a device."""
    try:
        # Capture initial device state
        initial_state = {}
        try:
            from phone_agent.device_factory import get_device_factory, set_device_type, DeviceType
            
            # Set device type
            device_type = req.device_type or "adb"
            if device_type == "hdc":
                set_device_type(DeviceType.HDC)
            elif device_type == "ios":
                set_device_type(DeviceType.IOS)
            else:
                set_device_type(DeviceType.ADB)
            
            factory = get_device_factory()
            
            # IMPORTANT: Reset to home screen first page before starting recording
            # This ensures consistent starting state
            await _reset_to_home_first_page(factory, req.device_id, device_type)
            
            # Get current app (should be home screen launcher now)
            try:
                current_app = factory.get_current_app(device_id=req.device_id)
                initial_state["current_app"] = current_app
            except Exception as e:
                print(f"Warning: Failed to get current app: {e}")
                initial_state["current_app"] = "Unknown"
            
            # Get screen dimensions if available (try to get from screenshot)
            try:
                screenshot = factory.get_screenshot(device_id=req.device_id, timeout=5)
                if screenshot:
                    initial_state["screen_width"] = screenshot.width
                    initial_state["screen_height"] = screenshot.height
                    # Store original dimensions if available
                    if hasattr(screenshot, 'original_width') and screenshot.original_width:
                        initial_state["original_screen_width"] = screenshot.original_width
                    if hasattr(screenshot, 'original_height') and screenshot.original_height:
                        initial_state["original_screen_height"] = screenshot.original_height
            except Exception as e:
                print(f"Warning: Failed to get screen dimensions from screenshot: {e}")
                # Try alternative method for ADB
                try:
                    if device_type == "adb":
                        import subprocess
                        result = subprocess.run(
                            ["adb", "-s", req.device_id, "shell", "wm", "size"],
                            capture_output=True, text=True, timeout=2
                        )
                        if result.returncode == 0:
                            # Parse output like "Physical size: 1080x2340"
                            import re
                            match = re.search(r'(\d+)x(\d+)', result.stdout)
                            if match:
                                initial_state["screen_width"] = int(match.group(1))
                                initial_state["screen_height"] = int(match.group(2))
                except Exception as e2:
                    print(f"Warning: Failed to get screen dimensions via shell: {e2}")
                    pass  # Screen info is optional
            
            # Get device info
            initial_state["device_id"] = req.device_id
            initial_state["device_type"] = device_type
            initial_state["timestamp"] = time.time()
            
        except Exception as e:
            print(f"Warning: Failed to capture initial state: {e}")
            # Continue with empty initial_state if capture fails
            initial_state = {
                "device_id": req.device_id,
                "device_type": req.device_type or "adb",
                "timestamp": time.time(),
                "current_app": "Unknown"
            }
        
        recording_id = recording_manager.start_recording(
            req.device_id, 
            req.device_type or "adb",
            initial_state=initial_state
        )
        return {"status": "started", "recording_id": recording_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop/{device_id}")
async def stop_recording(device_id: str):
    """Stop recording for a device."""
    try:
        recording_id = recording_manager.stop_recording(device_id)
        if not recording_id:
            raise HTTPException(status_code=404, detail="No active recording found")
        return {"status": "stopped", "recording_id": recording_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{device_id}")
async def get_recording_status(device_id: str):
    """Get recording status for a device."""
    is_recording = recording_manager.is_recording(device_id)
    recording_data = recording_manager.get_active_recording_data(device_id)
    
    return {
        "is_recording": is_recording,
        "recording_id": recording_data["id"] if recording_data else None,
        "action_count": len(recording_data["actions"]) if recording_data else 0
    }

@router.get("/preview/{recording_id}")
async def preview_recording(recording_id: str):
    """Get preview of an unsaved recording (actions list)."""
    # Try to find the recording in active recordings
    recording_data = None
    for device_id, data in list(recording_manager._active_recordings.items()):
        if data.get("id") == recording_id:
            recording_data = data
            break
    
    if not recording_data:
        raise HTTPException(status_code=404, detail="Recording not found")
    
    # Convert actions to dict format
    actions_list = []
    for action in recording_data.get("actions", []):
        # Handle both dict and RecordedAction object
        if isinstance(action, dict):
            actions_list.append({
                "action_type": action.get("action_type", ""),
                "timestamp": action.get("timestamp", 0.0),
                "params": action.get("params", {})
            })
        else:
            # It's a RecordedAction object
            from dataclasses import asdict
            action_dict = asdict(action)
            actions_list.append({
                "action_type": action_dict.get("action_type", ""),
                "timestamp": action_dict.get("timestamp", 0.0),
                "params": action_dict.get("params", {})
            })
    
    return {
        "recording_id": recording_id,
        "device_id": recording_data.get("device_id", ""),
        "device_type": recording_data.get("device_type", "adb"),
        "action_count": len(actions_list),
        "actions": actions_list,
        "initial_state": recording_data.get("initial_state", {})
    }

@router.post("/save")
async def save_recording(req: SaveRecordingRequest):
    """Save a recording with metadata."""
    try:
        recording = recording_manager.save_recording(
            req.recording_id,
            req.name,
            req.keywords,
            req.description
        )
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found")
        return {"status": "saved", "recording": {
            "id": recording.id,
            "name": recording.name,
            "keywords": recording.keywords,
            "device_id": recording.device_id,
            "device_type": recording.device_type,
            "action_count": len(recording.actions),
            "created_at": recording.created_at,
            "updated_at": recording.updated_at,
            "description": recording.description,
            "initial_state": recording.initial_state
        }}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list")
async def list_recordings(device_id: Optional[str] = None, keyword: Optional[str] = None):
    """List all recordings, optionally filtered."""
    try:
        recordings = recording_manager.list_recordings(device_id, keyword)
        return {
            "recordings": [{
                "id": r.id,
                "name": r.name,
                "keywords": r.keywords,
                "device_id": r.device_id,
                "device_type": r.device_type,
                "action_count": len(r.actions),
                "created_at": r.created_at,
                "updated_at": r.updated_at,
                "description": r.description,
                "initial_state": r.initial_state
            } for r in recordings]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{recording_id}")
async def get_recording(recording_id: str):
    """Get a recording by ID."""
    try:
        recording = recording_manager.get_recording(recording_id)
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found")
        return {
            "id": recording.id,
            "name": recording.name,
            "keywords": recording.keywords,
            "device_id": recording.device_id,
            "device_type": recording.device_type,
            "actions": [{
                "action_type": action.action_type,
                "timestamp": action.timestamp,
                "params": action.params
            } for action in recording.actions],
            "created_at": recording.created_at,
            "updated_at": recording.updated_at,
            "description": recording.description,
            "initial_state": recording.initial_state
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{recording_id}")
async def delete_recording(recording_id: str):
    """Delete a recording."""
    try:
        success = recording_manager.delete_recording(recording_id)
        if not success:
            raise HTTPException(status_code=404, detail="Recording not found")
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _get_recording_object(recording_id: str) -> Optional[Recording]:
    """Helper to get recording from saved or active recordings."""
    # First try to get from saved recordings
    recording = recording_manager.get_recording(recording_id)
    
    # If not found, try to get from active (unsaved) recordings
    if not recording:
        recording_data = None
        for device_id, data in recording_manager._active_recordings.items():
            if data["id"] == recording_id:
                recording_data = data
                break
        
        if recording_data:
            # Create a temporary Recording object from active recording data
            from datetime import datetime
            actions = []
            for action in recording_data["actions"]:
                if isinstance(action, dict):
                    actions.append(RecordedAction(**action))
                else:
                    actions.append(RecordedAction(**asdict(action)))
            
            recording = Recording(
                id=recording_id,
                name="Preview Recording",
                keywords=[],
                device_id=recording_data["device_id"],
                device_type=recording_data["device_type"],
                actions=actions,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                initial_state=recording_data.get("initial_state")
            )
    
    return recording

@router.post("/{recording_id}/execute")
async def execute_recording(recording_id: str, req: ExecuteRecordingRequest):
    """Execute a saved or unsaved recording."""
    try:
        recording = _get_recording_object(recording_id)
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found")
        
        # Use provided device_id or recording's device_id
        target_device_id = req.device_id or recording.device_id
        
        # Import here to avoid circular imports
        from ..services.recording_executor import execute_recording_actions
        
        # Run async function in thread pool to avoid blocking the main event loop
        # Create a new event loop in the thread
        def run_async():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                return new_loop.run_until_complete(execute_recording_actions(recording, target_device_id))
            finally:
                new_loop.close()
        
        loop = asyncio.get_event_loop()
        success, message = await loop.run_in_executor(_recording_executor, run_async)
        
        if not success:
            raise HTTPException(status_code=500, detail=message)
        
        return {"status": "executed", "message": message}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{recording_id}/reset")
async def reset_recording_state(recording_id: str, req: ExecuteRecordingRequest):
    """Reset device to initial state of the recording."""
    try:
        recording = _get_recording_object(recording_id)
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found")
        
        # Use provided device_id or recording's device_id
        target_device_id = req.device_id or recording.device_id
        
        from ..services.recording_executor import reset_to_initial_state
        
        # Run async function in thread pool to avoid blocking the main event loop
        def run_async():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                return new_loop.run_until_complete(reset_to_initial_state(recording, target_device_id))
            finally:
                new_loop.close()
        
        loop = asyncio.get_event_loop()
        success, message = await loop.run_in_executor(_recording_executor, run_async)
        
        if not success:
            raise HTTPException(status_code=500, detail=message)
        
        return {"status": "reset", "message": message}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{recording_id}/execute-action")
async def execute_single_action(recording_id: str, req: ExecuteSingleActionRequest):
    """Execute a single action from a recording."""
    try:
        recording = _get_recording_object(recording_id)
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found")
        
        if req.action_index < 0 or req.action_index >= len(recording.actions):
            raise HTTPException(status_code=400, detail="Invalid action index")
        
        action = recording.actions[req.action_index]
        target_device_id = req.device_id or recording.device_id
        
        from ..services.recording_executor import execute_single_action as exec_action
        
        # Run async function in thread pool to avoid blocking the main event loop
        def run_async():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                return new_loop.run_until_complete(exec_action(action, target_device_id, recording.device_type))
            finally:
                new_loop.close()
        
        loop = asyncio.get_event_loop()
        success, message = await loop.run_in_executor(_recording_executor, run_async)
        
        if not success:
            raise HTTPException(status_code=500, detail=message)
        
        return {"status": "executed", "message": message, "action_index": req.action_index}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{recording_id}/replace-action")
async def replace_action(recording_id: str, req: ReplaceActionRequest):
    """Replace an action in a recording (for re-recording)."""
    try:
        # Check if it's an active (unsaved) recording
        recording_data = None
        for device_id, data in recording_manager._active_recordings.items():
            if data["id"] == recording_id:
                recording_data = data
                break
        
        if not recording_data:
            raise HTTPException(status_code=404, detail="Recording not found or already saved. Can only replace actions in unsaved recordings.")
        
        actions = recording_data["actions"]
        if req.action_index < 0 or req.action_index >= len(actions):
            raise HTTPException(status_code=400, detail="Invalid action index")
        
        # Replace the action
        new_action = RecordedAction(**req.new_action)
        actions[req.action_index] = new_action
        
        return {
            "status": "replaced",
            "action_index": req.action_index,
            "action": {
                "action_type": new_action.action_type,
                "timestamp": new_action.timestamp,
                "params": new_action.params
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

