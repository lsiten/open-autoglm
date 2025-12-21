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
from phone_agent.adb.device import get_installed_packages
from phone_agent.config.apps import APP_PACKAGES
from .device_manager import device_manager
from .task_manager import task_manager, AgentTask
from .stream_manager import stream_manager
from .screen_streamer import screen_streamer
from .config_manager import config_manager

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

    def _is_confirmation_question(self, message: str) -> bool:
        """
        Determine if a message is a confirmation question (Yes/No) 
        or requires actual input (password, account, code, etc.).
        """
        message_lower = message.lower()
        
        # Keywords that indicate input is needed (password, account, code, etc.)
        input_keywords = [
            "密码", "password", "pwd",
            "账号", "账户", "account", "username", "user name",
            "验证码", "verification code", "verification", "code",
            "输入", "enter", "请输入", "please enter",
            "提供", "provide", "填写", "fill in"
        ]
        
        # Keywords that indicate confirmation question (Yes/No)
        confirmation_keywords = [
            "是否需要", "是否", "需要我", "是否允许", "是否同意",
            "do you need", "do you want", "would you like", 
            "should i", "may i", "can i", "是否要", "要不要",
            "是否安装", "是否下载", "是否继续", "是否执行",
            "install", "download", "continue", "proceed"
        ]
        
        # Check for input keywords first (higher priority)
        for keyword in input_keywords:
            if keyword in message_lower:
                return False
        
        # Check for confirmation keywords
        for keyword in confirmation_keywords:
            if keyword in message_lower:
                return True
        
        # Default: if message is short and ends with question mark, likely confirmation
        # Otherwise, assume it needs input
        if len(message.strip()) < 50 and message.strip().endswith(("?", "？")):
            return True
        
        return False

    def _input_callback(self, task_id: str, message: str) -> str:
        """
        Callback for requesting user input.
        Intelligently determines if this is a confirmation question (Yes/No)
        or requires actual input (password, account, code, etc.).
        Blocks until user responds via API.
        """
        is_confirmation = self._is_confirmation_question(message)
        
        if is_confirmation:
            self._emit_log(task_id, "warn", f"Waiting for confirmation: {message}")
        else:
            self._emit_log(task_id, "warn", f"Waiting for input: {message}")
        
        event = threading.Event()
        self.pending_interactions[task_id] = {"event": event, "response": None}
        
        # Send UI Card - determine type based on message content
        if self.main_loop and self.main_loop.is_running():
            if is_confirmation:
                # Send confirmation UI with Yes/No buttons
                # Don't set title, let frontend use i18n default
                asyncio.run_coroutine_threadsafe(
                    stream_manager.broadcast({
                        "type": "interaction",
                        "taskId": task_id,
                        "data": {
                            "type": "confirm",
                            "content": message,
                            "options": [
                                {"label": "No", "value": "No", "type": "danger"},
                                {"label": "Yes", "value": "Yes", "type": "success"}
                            ]
                        }
                    }),
                    self.main_loop
                )
            else:
                # Send input UI with text field
                # Don't set title, let frontend use i18n default
                asyncio.run_coroutine_threadsafe(
                    stream_manager.broadcast({
                        "type": "interaction",
                        "taskId": task_id,
                        "data": {
                            "type": "input",
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
        
        if is_confirmation:
            self._emit_log(task_id, "info", f"User confirmed: {response}")
        else:
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
            "detection_lock": detection_lock,
            "device_id": task.device_id
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

    def _get_all_installed_apps(self, device_id: str, user_apps: list = None) -> list:
        """
        Get all installed apps including system apps for LLM.
        
        Args:
            device_id: Device ID
            user_apps: Optional list of user apps from frontend (may be None or incomplete)
        
        Returns:
            List of all apps with name, package, and type fields
        """
        try:
            # Get all packages including system apps
            all_packages = get_installed_packages(device_id, include_system=True)
            user_packages = get_installed_packages(device_id, include_system=False)
            user_pkg_set = set(user_packages)
            
            # System packages = all packages - user packages
            system_packages = set(all_packages) - user_pkg_set
            
            # Invert APP_PACKAGES for lookup: package -> name
            pkg_to_name = {v: k for k, v in APP_PACKAGES.items()}
            
            # Get system app mappings from config to update system app names
            system_app_mappings = config_manager.get_system_app_mappings()
            # Create reverse mapping: package -> keyword (app name from config)
            # If a package appears in multiple keywords, use the first one found
            pkg_to_config_name = {}
            for keyword, packages in system_app_mappings.items():
                for pkg in packages:
                    if pkg not in pkg_to_config_name:
                        pkg_to_config_name[pkg] = keyword
            
            apps = []
            added_pkgs = set()
            
            # 1. Add all user packages
            for pkg in user_packages:
                name = pkg_to_name.get(pkg, pkg)
                is_supported = pkg in pkg_to_name
                apps.append({"name": name, "package": pkg, "type": "supported" if is_supported else "other"})
                added_pkgs.add(pkg)
            
            # 2. Add all system apps with names from config if available
            for pkg in system_packages:
                if pkg not in added_pkgs:
                    # Priority: config name > APP_PACKAGES name > package name
                    name = pkg_to_config_name.get(pkg) or pkg_to_name.get(pkg) or pkg
                    is_supported = pkg in pkg_to_name
                    apps.append({"name": name, "package": pkg, "type": "supported" if is_supported else "system"})
                    added_pkgs.add(pkg)
            
            return apps
        except Exception as e:
            print(f"Error getting all installed apps: {e}")
            # Fallback to user_apps if provided, or empty list
            return user_apps if user_apps else []
    
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
            # Get screenshot for starting task log
            start_screenshot = self._get_screenshot_for_task(task.id)
            self._emit_log(task.id, "info", f"Starting task: {display_name}", start_screenshot)
            
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

            # Get app matching config from config_manager
            system_app_mappings = config_manager.get_system_app_mappings()
            llm_prompt_template = config_manager.get_llm_prompt_template()
            system_prompt = config_manager.get_system_prompt(lang="cn")
            
            # Get all installed apps including system apps for LLM
            # Frontend only sends user-installed apps, so we need to fetch all apps here
            all_apps_for_llm = self._get_all_installed_apps(device_id, installed_apps)
            
            agent = PhoneAgent(
                model_config=model_config,
                agent_config=AgentConfig(
                    device_id=device_id,
                    verbose=True,
                    installed_apps=all_apps_for_llm,
                    system_app_mappings=system_app_mappings,
                    llm_prompt_template=llm_prompt_template,
                    system_prompt=system_prompt
                ),
                confirmation_callback=lambda msg: self._confirmation_callback(task.id, msg),
                input_callback=lambda msg: self._input_callback(task.id, msg),
                takeover_callback=lambda msg: self._takeover_callback(task.id, msg)
            )
            
            step_count = 0
            max_steps = 50 # Or infinite for background task?
            if task.type == 'background':
                max_steps = 1000 # Larger limit
            
            # Get screenshot for analyzing screen log
            analyze_screenshot = self._get_screenshot_for_task(task.id)
            self._emit_log(task.id, "info", "Analyzing screen...", analyze_screenshot)
            
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
                        # Get screenshot for step log
                        step_screenshot = self._get_screenshot_for_task(task.id)
                        self._emit_log(task.id, "info", f"Step {step_count}...", step_screenshot)
                        
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
                        # Get screenshot for detection cycle log
                        cycle_screenshot = self._get_screenshot_for_task(task.id)
                        if screen_changed:
                            self._emit_log(task.id, "info", "Starting detection cycle due to screen change...", cycle_screenshot)
                        else:
                            self._emit_log(task.id, "info", "Starting periodic detection cycle...", cycle_screenshot)
                        result = agent.step(final_prompt, on_token=on_token)
                        self._handle_step_result(task.id, result)
                    finally:
                        if detection_lock:
                            detection_lock.release()
            else:
                # For chat tasks, run normally
                while not result.finished and step_count < max_steps and not stop_event.is_set():
                    step_count += 1
                    # Get screenshot for step log
                    step_screenshot = self._get_screenshot_for_task(task.id)
                    self._emit_log(task.id, "info", f"Step {step_count}...", step_screenshot)
                    
                    result = agent.step(on_token=on_token)
                    self._handle_step_result(task.id, result)
            
            if stop_event.is_set():
                 self._emit_log(task.id, "warn", "Task stopped by user.")
                 task_manager.update_status(task.id, "stopped")
                 self._emit_status(task.id, "stopped")
            elif task.type != 'background' and result.finished:
                 # Check if task completed successfully or failed
                 # Check both result.success and message content for failure indicators
                 finish_message = result.message or ""
                 is_failure = self._is_failure_message(finish_message, result.success)
                 
                 if is_failure:
                     # Task finished but failed
                     # Error message already logged in _handle_step_result, just update status
                     failure_reason = finish_message or "任务执行失败，原因未知"
                     task_manager.update_status(task.id, "error")
                     self._emit_status(task.id, "error")
                 else:
                     # Task completed successfully
                     self._emit_log(task.id, "success", f"Task completed: {finish_message}")
                     task_manager.update_status(task.id, "completed")
                     self._emit_status(task.id, "completed")
            elif task.type != 'background':
                 # Task cannot be completed - reached max steps
                 self._emit_log(task.id, "error", "无法完成任务：已达到最大执行步数，任务可能过于复杂或无法在当前条件下完成。")
                 task_manager.update_status(task.id, "error")
                 self._emit_status(task.id, "error")
            
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

    def _get_screenshot_for_task(self, task_id: str) -> str:
        """Get screenshot for a task. Returns base64 string or None."""
        try:
            task_data = self.active_tasks.get(task_id)
            if task_data:
                device_id = task_data.get("device_id")
                if device_id:
                    # Always try to get screenshot directly from device first
                    # This ensures we get the most up-to-date screenshot
                    factory = get_device_factory()
                    screenshot = factory.get_screenshot(device_id, quality=50, max_width=540)
                    if screenshot and screenshot.base64_data:
                        return screenshot.base64_data
                    # Fallback: try screen_streamer if direct capture fails
                    if screen_streamer.latest_frame:
                        import base64
                        return base64.b64encode(screen_streamer.latest_frame).decode('utf-8')
        except Exception as e:
            # Don't fail if screenshot capture fails, but log for debugging
            # print(f"[AgentRunner] Failed to get screenshot for task {task_id}: {e}")
            pass
        return None

    def _is_failure_message(self, message: str, result_success: bool) -> bool:
        """Check if a finish message indicates task failure."""
        if not result_success:
            return True
        
        if not message:
            return False
        
        failure_keywords = [
            "无法完成", "不能完成", "无法实现", "不能实现",
            "失败", "错误", "异常",
            "cannot", "unable", "failed", "error", "exception",
            "未找到", "找不到", "not found", "missing",
            "无法安装", "不能安装", "cannot install",
            "无法打开", "不能打开", "cannot open",
        ]
        
        message_lower = message.lower()
        for keyword in failure_keywords:
            if keyword.lower() in message_lower:
                return True
        return False

    def _handle_step_result(self, task_id: str, result: StepResult):
        # Get screenshot for this step
        screenshot_base64 = self._get_screenshot_for_task(task_id)
        
        if result.thinking:
            self._emit_log(task_id, "thought", result.thinking, screenshot_base64)
        
        if result.action:
            if result.finished:
                # If finished, check if it's a failure based on message content
                finish_message = result.message or ""
                is_failure = self._is_failure_message(finish_message, result.success)
                
                if is_failure:
                    # Log as error for failed finish
                    self._emit_log(task_id, "error", f"无法完成任务：{finish_message}", screenshot_base64)
                else:
                    # Log as action for successful finish (will be handled by completion logic)
                    action_str = json.dumps(result.action, ensure_ascii=False)
                    self._emit_log(task_id, "action", action_str, screenshot_base64)
            else:
                # Format action for display
                action_str = json.dumps(result.action, ensure_ascii=False)
                self._emit_log(task_id, "action", action_str, screenshot_base64)

    def _emit_log(self, task_id: str, level: str, message: str, screenshot: str = None):
        # Store in DB
        task_manager.add_log(task_id, level, message, screenshot)
        
        # Broadcast to frontend
        if self.main_loop and self.main_loop.is_running():
            log_data = {
                "type": "log",
                "taskId": task_id,
                "level": level,
                "message": message
            }
            if screenshot:
                log_data["screenshot"] = screenshot
            asyncio.run_coroutine_threadsafe(
                stream_manager.broadcast(log_data),
                self.main_loop
            )
        else:
            print(f"[{task_id}] {level}: {message}")

    def _emit_event(self, event_type: str, data: Dict[str, Any]):
        pass # Deprecated or update to use broadcast

agent_runner = AgentRunner.get_instance()
