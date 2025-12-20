import threading
import asyncio
import traceback
import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any
from phone_agent.agent import PhoneAgent, AgentConfig, StepResult
from phone_agent.model import ModelConfig
from phone_agent.device_factory import get_device_factory, set_device_type, DeviceType
from .device_manager import device_manager
from .task_manager import task_manager, AgentTask
from .stream_manager import stream_manager
from .screen_streamer import screen_streamer

class AgentRunner:
    _instance = None
    
    def __init__(self):
        self.active_tasks: Dict[str, Dict[str, Any]] = {} # task_id -> {thread, stop_event, screen_change_event}
        self.pending_interactions: Dict[str, Dict[str, Any]] = {} # task_id -> {event, response}
        self.main_loop = None
        # Thread pool for handling screen change triggered detections
        self.detection_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="task-detection")
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

    def _input_callback(self, task_id: str, message: str) -> str:
        """
        Callback for requesting user input.
        Blocks until user responds via API.
        """
        self._emit_log(task_id, "warn", f"Waiting for input: {message}")
        
        event = threading.Event()
        self.pending_interactions[task_id] = {"event": event, "response": None}
        
        # Send UI Card
        if self.main_loop and self.main_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                stream_manager.broadcast({
                    "type": "interaction",
                    "taskId": task_id,
                    "data": {
                        "type": "input",
                        "title": "Input Required",
                        "content": message,
                        "placeholder": "Enter value..."
                    }
                }),
                self.main_loop
            )
            
        task_data = self.active_tasks.get(task_id)
        while not event.is_set():
            if task_data and task_data["stop_event"].is_set():
                del self.pending_interactions[task_id]
                return ""
            time.sleep(0.5)
            
        response = self.pending_interactions[task_id]["response"]
        del self.pending_interactions[task_id]
        
        self._emit_log(task_id, "info", f"User provided input: {response}")
        return str(response)

    def _takeover_callback(self, task_id: str, message: str) -> None:
        """
        Callback for takeover request.
        Blocks until user confirms completion.
        """
        self._emit_log(task_id, "warn", f"Manual Takeover: {message}")
        
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
                        "title": "Manual Takeover Required",
                        "content": message,
                        "options": [
                            {"label": "I have finished", "value": "Done", "type": "success"}
                        ]
                    }
                }),
                self.main_loop
            )
            
        task_data = self.active_tasks.get(task_id)
        while not event.is_set():
            if task_data and task_data["stop_event"].is_set():
                del self.pending_interactions[task_id]
                return
            time.sleep(0.5)
            
        del self.pending_interactions[task_id]
        self._emit_log(task_id, "info", "User finished manual takeover.")

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
        screen_change_event = threading.Event()  # Event to trigger immediate check on screen change
        detection_lock = threading.Lock()  # Lock to prevent concurrent detections for the same task
        
        # Register screen change listener for background tasks
        def on_screen_change():
            if task_id in self.active_tasks and task.type == 'background':
                # Trigger detection in a separate thread to avoid blocking screen capture
                screen_change_event.set()
                # Submit detection execution to thread pool
                self.detection_executor.submit(self._trigger_detection, task_id)
        
        if task.type == 'background':
            screen_streamer.register_screen_change_listener(on_screen_change)
        
        thread = threading.Thread(
            target=self._run_agent_loop,
            args=(task, stop_event, prompt_override, installed_apps, screen_change_event)
        )
        self.active_tasks[task_id] = {
            "thread": thread, 
            "stop_event": stop_event,
            "screen_change_event": screen_change_event,
            "screen_change_callback": on_screen_change,
            "detection_lock": detection_lock
        }
        thread.start()
        task_manager.update_status(task_id, "running")
        self._emit_status(task_id, "running")
        return True, "Task started"
    
    def _trigger_detection(self, task_id: str):
        """Trigger detection for a background task in a separate thread."""
        if task_id not in self.active_tasks:
            return
        
        task_data = self.active_tasks[task_id]
        detection_lock = task_data.get("detection_lock")
        
        # Use lock to prevent concurrent detections
        if detection_lock and detection_lock.acquire(blocking=False):
            try:
                # The actual detection will be handled by the main task loop
                # This just ensures the event is set and logged
                self._emit_log(task_id, "info", "Screen change detected, queuing detection...")
            finally:
                detection_lock.release()

    def stop_task(self, task_id: str = None):
        if task_id:
            if task_id in self.active_tasks:
                task_data = self.active_tasks[task_id]
                task_data["stop_event"].set()
                # Unregister screen change listener
                if "screen_change_callback" in task_data:
                    screen_streamer.unregister_screen_change_listener(task_data["screen_change_callback"])
                return True
            return False
        else:
            for tid, data in self.active_tasks.items():
                data["stop_event"].set()
                # Unregister screen change listener
                if "screen_change_callback" in data:
                    screen_streamer.unregister_screen_change_listener(data["screen_change_callback"])
            return True

    def _run_agent_loop(self, task: AgentTask, stop_event: threading.Event, prompt_override: str = None, installed_apps: list = None, screen_change_event: threading.Event = None):
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
                confirmation_callback=lambda msg: self._confirmation_callback(task.id, msg),
                input_callback=lambda msg: self._input_callback(task.id, msg),
                takeover_callback=lambda msg: self._takeover_callback(task.id, msg)
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
            
            # For background tasks, run in a continuous loop
            if task.type == 'background':
                check_interval = 30  # Check every 30 seconds
                while not stop_event.is_set():
                    step_count = 0
                    # Run one detection cycle
                    while not result.finished and step_count < max_steps and not stop_event.is_set():
                        step_count += 1
                        self._emit_log(task.id, "info", f"Step {step_count}...")
                        
                        result = agent.step(on_token=on_token)
                        self._handle_step_result(task.id, result)
                    
                    if stop_event.is_set():
                        break
                    
                    # If task finished (found something to do), log it
                    if result.finished:
                        self._emit_log(task.id, "success", f"Task cycle completed: {result.message}")
                        # Reset for next cycle
                        result.finished = False
                    
                    # Wait before next check cycle, but also listen for screen changes
                    self._emit_log(task.id, "info", f"Waiting for screen change or {check_interval} seconds before next check...")
                    # Wait in smaller intervals to allow stop_event and screen_change_event to be checked
                    waited = 0
                    screen_changed = False
                    while waited < check_interval and not stop_event.is_set():
                        # Check for screen change every second
                        if screen_change_event and screen_change_event.is_set():
                            screen_change_event.clear()
                            screen_changed = True
                            self._emit_log(task.id, "info", "Screen change detected! Triggering immediate check...")
                            break
                        time.sleep(1)
                        waited += 1
                    
                    if stop_event.is_set():
                        break
                    
                    # Start new detection cycle (either triggered by screen change or timeout)
                    # Use lock to ensure detection runs in a controlled manner in separate thread context
                    detection_lock = self.active_tasks.get(task.id, {}).get("detection_lock")
                    if detection_lock:
                        detection_lock.acquire()
                    
                    try:
                        if screen_changed:
                            self._emit_log(task.id, "info", "Starting detection cycle due to screen change...")
                        else:
                            self._emit_log(task.id, "info", "Starting periodic detection cycle...")
                        result = agent.step(final_prompt, on_token=on_token)
                        self._handle_step_result(task.id, result)
                    finally:
                        if detection_lock:
                            detection_lock.release()
            else:
                # For chat tasks, run normally
                while not result.finished and step_count < max_steps and not stop_event.is_set():
                    step_count += 1
                    self._emit_log(task.id, "info", f"Step {step_count}...")
                    
                    result = agent.step(on_token=on_token)
                    self._handle_step_result(task.id, result)
            
            if stop_event.is_set():
                 self._emit_log(task.id, "warn", "Task stopped by user.")
                 task_manager.update_status(task.id, "stopped")
                 self._emit_status(task.id, "stopped")
            elif task.type != 'background' and result.finished:
                 # Only mark as completed for non-background tasks
                 self._emit_log(task.id, "success", f"Task completed: {result.message}")
                 task_manager.update_status(task.id, "completed")
                 self._emit_status(task.id, "completed")
            elif task.type != 'background':
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
                task_data = self.active_tasks[task.id]
                # Unregister screen change listener
                if "screen_change_callback" in task_data:
                    screen_streamer.unregister_screen_change_listener(task_data["screen_change_callback"])
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
