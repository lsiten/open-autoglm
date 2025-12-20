import threading
import asyncio
import traceback
import json
import time
from typing import Optional, Dict, Any
from phone_agent.agent import PhoneAgent, AgentConfig, StepResult
from phone_agent.model import ModelConfig
from phone_agent.device_factory import get_device_factory, set_device_type, DeviceType
from .device_manager import device_manager
from .task_manager import task_manager, AgentTask
from .stream_manager import stream_manager

class AgentRunner:
    _instance = None
    
    def __init__(self):
        self.active_tasks: Dict[str, Dict[str, Any]] = {} # task_id -> {thread, stop_event}
        self.pending_interactions: Dict[str, Dict[str, Any]] = {} # task_id -> {event, response}
        self.main_loop = None
        # Default config
        self.base_url = "http://localhost:8080/v1"
        self.model_name = "autoglm-phone-9b"
        self.api_key = "EMPTY"

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def update_config(self, base_url: str, model: str, api_key: str):
        self.base_url = base_url
        self.model_name = model
        self.api_key = api_key

    def handle_interaction_response(self, task_id: str, response_data: Any):
        if task_id in self.pending_interactions:
            interaction = self.pending_interactions[task_id]
            interaction["response"] = response_data
            if "event" in interaction:
                interaction["event"].set()
            return True
        return False

    def _confirmation_callback(self, task_id: str, message: str) -> bool:
        """
        Callback for sensitive action confirmation.
        Blocks until user responds via API.
        """
        # Parse permission key if present: "[PERMISSION:key] message"
        permission_key = None
        clean_message = message
        if message.startswith("[PERMISSION:"):
            try:
                end_idx = message.index("]")
                permission_key = message[12:end_idx]
                clean_message = message[end_idx+1:].strip()
            except ValueError:
                pass
        
        # Check auto-permission
        if permission_key:
            task = task_manager.get_task(task_id)
            if task:
                perms = device_manager.get_device_permissions(task.device_id)
                if perms.get(permission_key, False):
                    self._emit_log(task_id, "info", f"Auto-approved sensitive action: {clean_message}")
                    return True

        # Need manual confirmation
        self._emit_log(task_id, "warn", f"Waiting for confirmation: {clean_message}")
        
        # Setup interaction wait
        event = threading.Event()
        self.pending_interactions[task_id] = {"event": event, "response": None}
        
        # Send UI Card
        if self.main_loop and self.main_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                stream_manager.broadcast({
                    "type": "interaction",
                    "taskId": task_id,
                    "data": {
                        "type": "confirm",
                        "title": "Sensitive Action Permission",
                        "content": clean_message,
                        "options": [
                            {"label": "Deny", "value": "No", "type": "danger"},
                            {"label": "Allow", "value": "Yes", "type": "success"}
                        ]
                    }
                }),
                self.main_loop
            )
        
        # Block and wait
        # We should check stop_event occasionally to allow cancellation
        # But here we are inside the thread, so we can just wait on event
        # However, we also need to respect task cancellation
        task_data = self.active_tasks.get(task_id)
        
        while not event.is_set():
            if task_data and task_data["stop_event"].is_set():
                del self.pending_interactions[task_id]
                return False
            time.sleep(0.5)
            
        response = self.pending_interactions[task_id]["response"]
        del self.pending_interactions[task_id]
        
        approved = response == "Yes" or response == "Allow"
        if approved:
            self._emit_log(task_id, "info", "User approved action.")
        else:
            self._emit_log(task_id, "warn", "User denied action.")
            
        return approved

    # Legacy method wrapper for backward compatibility
    def start_task(self, prompt: str):
        device_id = device_manager.active_device_id
        if not device_id:
            return False, "No device selected"
            
        # Create a temporary/default chat session
        task = task_manager.create_task(
            device_id=device_id,
            type="chat",
            name="Chat Session",
            details=prompt
        )
        return self.start_session(task.id)

    def _emit_status(self, task_id: str, status: str):
        # Broadcast status to frontend
        if self.main_loop and self.main_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                stream_manager.broadcast({
                    "type": "status",
                    "taskId": task_id,
                    "data": {
                        "state": status
                    }
                }),
                self.main_loop
            )

    def start_session(self, task_id: str, prompt_override: str = None, installed_apps: list = None):
        task = task_manager.get_task(task_id)
        if not task:
            return False, "Task not found"
            
        if task_id in self.active_tasks:
            return False, "Task already running"

        # Capture main loop
        try:
            self.main_loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        stop_event = threading.Event()
        thread = threading.Thread(
            target=self._run_agent_loop,
            args=(task, stop_event, prompt_override, installed_apps)
        )
        self.active_tasks[task_id] = {"thread": thread, "stop_event": stop_event}
        thread.start()
        task_manager.update_status(task_id, "running")
        self._emit_status(task_id, "running")
        return True, "Task started"

    def stop_task(self, task_id: str = None):
        # ... existing ...
        if task_id:
            if task_id in self.active_tasks:
                self.active_tasks[task_id]["stop_event"].set()
                return True
            return False
        else:
            for tid, data in self.active_tasks.items():
                data["stop_event"].set()
            return True

    def _run_agent_loop(self, task: AgentTask, stop_event: threading.Event, prompt_override: str = None, installed_apps: list = None):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        device_id = task.device_id
        # Use override if provided, else details
        prompt = prompt_override if prompt_override else task.details
        
        # ... existing ...
        is_webrtc = any(d['id'] == device_id for d in device_manager.webrtc_devices)
        if is_webrtc:
            set_device_type(DeviceType.WEBRTC)
        else:
            set_device_type(DeviceType.ADB)
        
        try:
            display_name = prompt[:50] + "..." if len(prompt) > 50 else prompt
            self._emit_log(task.id, "info", f"Starting task: {display_name}")
            
            model_config = ModelConfig(
                base_url=self.base_url,
                model_name=self.model_name,
                api_key=self.api_key
            )
            
            # Construct Agent Prompt based on Role
            # If Role is set, prepend it?
            # For now, pass as system prompt if supported, or prepend to user prompt
            final_prompt = prompt
            if task.role:
                final_prompt = f"Role: {task.role}\nTask: {prompt}"

            agent = PhoneAgent(
                model_config=model_config,
                agent_config=AgentConfig(
                    device_id=device_id,
                    verbose=True,
                    installed_apps=installed_apps
                ),
                confirmation_callback=lambda msg: self._confirmation_callback(task.id, msg)
            )
            
            step_count = 0
            max_steps = 50 # Or infinite for background task?
            if task.type == 'background':
                max_steps = 1000 # Larger limit
            
            self._emit_log(task.id, "info", "Analyzing screen...")
            
            def on_token(token):
                self._emit_log(task.id, "thought", token)
                
            result = agent.step(final_prompt, on_token=on_token)
            self._handle_step_result(task.id, result)
            
            while not result.finished and step_count < max_steps and not stop_event.is_set():
                step_count += 1
                self._emit_log(task.id, "info", f"Step {step_count}...")
                
                # For background monitoring, we might need a delay?
                if task.type == 'background':
                    time.sleep(2) # Wait a bit between steps
                
                result = agent.step(on_token=on_token)
                self._handle_step_result(task.id, result)
            
            if stop_event.is_set():
                 self._emit_log(task.id, "warn", "Task stopped by user.")
                 task_manager.update_status(task.id, "stopped")
                 self._emit_status(task.id, "stopped")
            elif result.finished:
                 self._emit_log(task.id, "success", f"Task completed: {result.message}")
                 task_manager.update_status(task.id, "completed")
                 self._emit_status(task.id, "completed")
            else:
                 self._emit_log(task.id, "warn", "Max steps reached.")
                 task_manager.update_status(task.id, "stopped")
                 self._emit_status(task.id, "stopped")
            
        except Exception as e:
            traceback.print_exc()
            error_msg = str(e)
            self._emit_log(task.id, "error", f"Task failed: {error_msg}")
            task_manager.update_status(task.id, "error")
            self._emit_status(task.id, "error")
        finally:
            if task.id in self.active_tasks:
                del self.active_tasks[task.id]
            loop.close()

    def _handle_step_result(self, task_id: str, result: StepResult):
        if result.thinking:
            self._emit_log(task_id, "thought", result.thinking)
        
        if result.action and not result.finished:
            # Format action for display
            action_str = json.dumps(result.action, ensure_ascii=False)
            self._emit_log(task_id, "action", action_str)

    def _emit_log(self, task_id: str, level: str, message: str):
        # Store in DB
        task_manager.add_log(task_id, level, message)
        
        # Broadcast to frontend
        if self.main_loop and self.main_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                stream_manager.broadcast({
                    "type": "log",
                    "taskId": task_id,
                    "level": level,
                    "message": message
                }),
                self.main_loop
            )
        else:
            print(f"[{task_id}] {level}: {message}")

    def _emit_event(self, event_type: str, data: Dict[str, Any]):
        pass # Deprecated or update to use broadcast

agent_runner = AgentRunner.get_instance()
