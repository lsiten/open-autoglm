"""Main PhoneAgent class for orchestrating phone automation."""

import json
import re
import time
import traceback
from dataclasses import dataclass
from typing import Any, Callable

from phone_agent.actions import ActionHandler
from phone_agent.actions.handler import ActionResult, do, finish, parse_action
from phone_agent.config import get_messages, get_system_prompt
from phone_agent.device_factory import get_device_factory
from phone_agent.model import ModelClient, ModelConfig
from phone_agent.model.client import MessageBuilder


@dataclass
class AgentConfig:
    """Configuration for the PhoneAgent."""

    max_steps: int = 100
    device_id: str | None = None
    lang: str = "cn"
    system_prompt: str | None = None
    verbose: bool = True
    installed_apps: list[dict[str, Any]] | None = None
    system_app_mappings: dict[str, list] | None = None
    llm_prompt_template: str | None = None
    available_recordings: list[dict[str, Any]] | None = None  # List of available recordings for AI to use

    def __post_init__(self):
        if self.system_prompt is None:
            self.system_prompt = get_system_prompt(self.lang)


@dataclass
class StepResult:
    """Result of a single agent step."""

    success: bool
    finished: bool
    action: dict[str, Any] | None
    thinking: str
    message: str | None = None
    annotated_screenshot: str | None = None  # Screenshot with click position marked (for Tap actions)


class PhoneAgent:
    """
    AI-powered agent for automating Android phone interactions.

    The agent uses a vision-language model to understand screen content
    and decide on actions to complete user tasks.

    Args:
        model_config: Configuration for the AI model.
        agent_config: Configuration for the agent behavior.
        confirmation_callback: Optional callback for sensitive action confirmation.
        takeover_callback: Optional callback for takeover requests.

    Example:
        >>> from phone_agent import PhoneAgent
        >>> from phone_agent.model import ModelConfig
        >>>
        >>> model_config = ModelConfig(base_url="http://localhost:8000/v1")
        >>> agent = PhoneAgent(model_config)
        >>> agent.run("Open WeChat and send a message to John")
    """

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        agent_config: AgentConfig | None = None,
        confirmation_callback: Callable[[str], bool] | None = None,
        takeover_callback: Callable[[str], None] | None = None,
        input_callback: Callable[[str], str] | None = None,
        click_annotation_callback: Callable[[str], dict] | None = None,
        status_callback: Callable[[str, dict], None] | None = None,  # Only used for long-running tasks like app installation
    ):
        self.model_config = model_config or ModelConfig()
        self.agent_config = agent_config or AgentConfig()

        self.model_client = ModelClient(self.model_config)
        
        self.action_handler = ActionHandler(
            device_id=self.agent_config.device_id,
            confirmation_callback=confirmation_callback,
            takeover_callback=takeover_callback,
            input_callback=input_callback,
            click_annotation_callback=click_annotation_callback,
            model_client=self.model_client,
            installed_apps=self.agent_config.installed_apps,
            system_app_mappings=self.agent_config.system_app_mappings,
            llm_prompt_template=self.agent_config.llm_prompt_template,
        )

        self._context: list[dict[str, Any]] = []
        self._step_count = 0
        # Track retry counts for actions: key is action signature, value is retry count
        self._action_retry_counts: dict[str, int] = {}
        
        # Store click_annotation_callback for user guidance
        self.click_annotation_callback = click_annotation_callback
        
        # Store status_callback for long-running task status updates
        # NOTE: Currently only used for app installation progress monitoring.
        # Other actions do not send progress messages.
        self.status_callback = status_callback

    def run(self, task: str) -> str:
        """
        Run the agent to complete a task.

        Args:
            task: Natural language description of the task.

        Returns:
            Final message from the agent.
        """
        self._context = []
        self._step_count = 0

        # First step with user prompt
        result = self._execute_step(task, is_first=True)

        if result.finished:
            return result.message or "Task completed"

        # Continue until finished or max steps reached
        while self._step_count < self.agent_config.max_steps:
            result = self._execute_step(is_first=False)

            if result.finished:
                return result.message or "Task completed"

        return "Max steps reached"

    def step(self, task: str | None = None, on_token: Callable[[str], None] = None) -> StepResult:
        """
        Execute a single step of the agent.

        Useful for manual control or debugging.

        Args:
            task: Task description (only needed for first step).
            on_token: Callback for streaming tokens.

        Returns:
            StepResult with step details.
        """
        is_first = len(self._context) == 0

        if is_first and not task:
            raise ValueError("Task is required for the first step")

        return self._execute_step(task, is_first, on_token=on_token)

    def reset(self) -> None:
        """Reset the agent state for a new task."""
        self._context = []
        self._step_count = 0
        self._action_retry_counts = {}

    def _check_and_wait_for_installations(self, device_factory) -> None:
        """
        Check if any apps are being installed and wait for them to complete.
        This is called before each step to ensure installations complete before proceeding.
        
        First confirms installation has started by analyzing screenshot, then waits for completion.
        
        NOTE: This is the ONLY place where status_callback is used to send progress messages.
        Other actions (Tap, Type, Swipe, etc.) do NOT send progress messages.
        """
        # Check current app - if we're in an app store or installer, we might be installing
        current_app = device_factory.get_current_app(
            self.agent_config.device_id,
            installed_apps=self.agent_config.installed_apps
        )
        
        # Common app store/installer package names
        installer_keywords = ["market", "store", "installer", "应用市场", "应用商店", "play store", "app store"]
        is_in_installer = any(kw in current_app.lower() for kw in installer_keywords)
        
        if not is_in_installer:
            return  # Not in installer, no need to check
        
        print(f"[Agent] Detected installer app: {current_app}, checking if installation has started...")
        
        # STEP 1: Get screenshot and confirm installation has started
        try:
            screenshot = device_factory.get_screenshot(self.agent_config.device_id)
        except Exception as e:
            print(f"[Agent] Error getting screenshot for installation check: {e}")
            return
        
        # Use AI to confirm installation has started
        installation_confirmed = False
        if self.model_client and screenshot.base64_data:
            try:
                # Ask AI to analyze if installation has started
                analysis_prompt = """请分析当前屏幕截图，判断是否正在进行应用安装。

请检查以下内容：
1. 是否显示"正在安装"、"安装中"、"下载中"等提示？
2. 是否显示安装进度条？
3. 是否显示"安装完成"、"安装成功"、"完成"等提示（表示已完成）？
4. 是否显示"安装失败"、"错误"等提示（表示已失败）？

请用JSON格式回答：{"installing": true/false, "completed": true/false, "failed": true/false, "message": "状态描述"}

如果正在安装，installing应该为true。如果已完成或失败，installing应该为false。"""
                
                from phone_agent.model.client import MessageBuilder
                analysis_message = MessageBuilder.create_user_message(
                    text=analysis_prompt,
                    image_base64=screenshot.base64_data
                )
                
                # Get AI response
                response = self.model_client.request([analysis_message], on_token=None)
                response_text = response.raw_content if hasattr(response, 'raw_content') else (response.action if hasattr(response, 'action') else str(response))
                
                # Try to find JSON in response
                json_match = re.search(r'\{[^{}]*"installing"[^{}]*\}', response_text, re.DOTALL)
                if json_match:
                    try:
                        installation_status = json.loads(json_match.group())
                        print(f"[Agent] AI analysis result: {installation_status}")
                        
                        # Check if installation has started
                        if installation_status.get("installing", False):
                            installation_confirmed = True
                            print(f"[Agent] Installation confirmed to be in progress")
                        elif installation_status.get("completed", False):
                            print(f"[Agent] Installation already completed")
                            return  # Already done, no need to wait
                        elif installation_status.get("failed", False):
                            print(f"[Agent] Installation failed")
                            if self.status_callback:
                                try:
                                    app_name = current_app if current_app and current_app.strip() else "应用市场"
                                    self.status_callback("installation_failed", {
                                        "app": app_name,
                                        "status": "安装失败",
                                        "message": installation_status.get("message", "安装失败") or "安装失败"
                                    })
                                except Exception as e:
                                    print(f"[Agent] Error in status callback: {e}")
                            return  # Failed, no need to wait
                        else:
                            print(f"[Agent] No installation detected in screenshot, not waiting")
                            return  # Not installing, no need to wait
                    except json.JSONDecodeError as e:
                        print(f"[Agent] Failed to parse AI response as JSON: {e}")
                        print(f"[Agent] Response text: {response_text[:200]}")
                else:
                    print(f"[Agent] No JSON found in AI response, assuming no installation")
                    return  # Can't confirm, don't wait
            except Exception as e:
                print(f"[Agent] Error analyzing installation with AI: {e}")
                import traceback
                traceback.print_exc()
                return  # Error in analysis, don't wait
        
        # If installation not confirmed, don't wait
        if not installation_confirmed:
            print(f"[Agent] Installation not confirmed, skipping wait")
            return
        
        # STEP 2: Installation confirmed, start waiting and monitoring
        print(f"[Agent] Installation confirmed, starting to wait for completion...")
        
        # Report status: installation detected and confirmed
        if self.status_callback:
            try:
                # Ensure current_app is not empty
                app_name = current_app if current_app and current_app.strip() else "应用市场"
                self.status_callback("installation_detected", {
                    "app": app_name,
                    "status": "检测到安装任务",
                    "message": f"已确认正在 {app_name} 中安装应用，等待安装完成..."
                })
            except Exception as e:
                print(f"[Agent] Error in status callback: {e}")
        
        # Wait and check installation status using AI analysis
        max_wait_time = 300  # 5 minutes max
        check_interval = 3  # Check every 3 seconds
        waited = 0
        last_status_message = None
        last_screenshot_hash = None
        consecutive_same_screenshots = 0
        
        while waited < max_wait_time:
            time.sleep(check_interval)
            waited += check_interval
            
            # Get current screenshot to analyze installation progress
            try:
                screenshot = device_factory.get_screenshot(self.agent_config.device_id)
                screenshot_hash = hash(screenshot.base64_data[:1000] if screenshot.base64_data else "")  # Simple hash for comparison
                
                # Check if screenshot changed (indicates progress)
                if screenshot_hash == last_screenshot_hash:
                    consecutive_same_screenshots += 1
                else:
                    consecutive_same_screenshots = 0
                last_screenshot_hash = screenshot_hash
                
                # Use AI to analyze installation progress if model is available
                installation_status = None
                if self.model_client and screenshot.base64_data:
                    try:
                        # Ask AI to analyze installation status
                        analysis_prompt = """请分析当前屏幕截图，判断应用安装的状态。请回答以下问题：
1. 是否正在安装应用？（是/否）
2. 如果正在安装，安装进度如何？（0-100%）
3. 是否显示"安装完成"、"安装成功"、"完成"等提示？（是/否）
4. 是否显示"安装失败"、"错误"等提示？（是/否）

请用JSON格式回答：{"installing": true/false, "progress": 0-100, "completed": true/false, "failed": true/false, "message": "状态描述"}"""
                        
                        # Create a simple message for AI analysis
                        from phone_agent.model.client import MessageBuilder
                        analysis_message = MessageBuilder.create_user_message(
                            text=analysis_prompt,
                            image_base64=screenshot.base64_data
                        )
                        
                        # Get AI response (simplified - just get the response, don't parse action)
                        response = self.model_client.request([analysis_message], on_token=None)
                        
                        # Try to extract JSON from response
                        # Use raw_content which contains the full response text
                        response_text = response.raw_content if hasattr(response, 'raw_content') else (response.action if hasattr(response, 'action') else str(response))
                        
                        # Try to find JSON in response
                        json_match = re.search(r'\{[^{}]*"installing"[^{}]*\}', response_text, re.DOTALL)
                        if json_match:
                            installation_status = json.loads(json_match.group())
                            print(f"[Agent] AI analysis: {installation_status}")
                    except Exception as e:
                        print(f"[Agent] Error analyzing installation with AI: {e}")
                
                # Check installation status from AI analysis
                if installation_status:
                    if installation_status.get("completed", False):
                        print(f"[Agent] Installation completed (detected by AI)")
                        if self.status_callback:
                            try:
                                app_name = current_app if current_app and current_app.strip() else "应用市场"
                                self.status_callback("installation_completed", {
                                    "app": app_name,
                                    "status": "安装完成",
                                    "message": installation_status.get("message", "安装已完成") or "安装已完成"
                                })
                            except Exception as e:
                                print(f"[Agent] Error in status callback: {e}")
                        # Wait a bit more to ensure UI updates
                        time.sleep(2)
                        break
                    
                    if installation_status.get("failed", False):
                        print(f"[Agent] Installation failed (detected by AI)")
                        if self.status_callback:
                            try:
                                app_name = current_app if current_app and current_app.strip() else "应用市场"
                                self.status_callback("installation_failed", {
                                    "app": app_name,
                                    "status": "安装失败",
                                    "message": installation_status.get("message", "安装失败") or "安装失败"
                                })
                            except Exception as e:
                                print(f"[Agent] Error in status callback: {e}")
                        break
                    
                    # Report progress if available
                    progress = installation_status.get("progress", None)
                    if progress is not None:
                        status_message = f"安装进度: {progress}%"
                        if status_message != last_status_message:
                            print(f"[Agent] {status_message}")
                            if self.status_callback:
                                try:
                                    app_name = current_app if current_app and current_app.strip() else "应用市场"
                                    self.status_callback("installation_progress", {
                                        "app": app_name,
                                        "status": "安装中",
                                        "message": status_message or "安装中...",
                                        "progress": progress / 100.0
                                    })
                                except Exception as e:
                                    print(f"[Agent] Error in status callback: {e}")
                            last_status_message = status_message
                    
                    # If not installing anymore and not completed/failed, might have been cancelled
                    if not installation_status.get("installing", False) and not installation_status.get("completed", False) and not installation_status.get("failed", False):
                        print(f"[Agent] Installation status unclear, might have been cancelled")
                        break
                
            except Exception as e:
                print(f"[Agent] Error checking installation status: {e}")
            
            # Check if we're still in installer
            current_app_after = device_factory.get_current_app(
                self.agent_config.device_id,
                installed_apps=self.agent_config.installed_apps
            )
            
            # If we're no longer in installer, installation might be complete
            if not any(kw in current_app_after.lower() for kw in installer_keywords):
                print(f"[Agent] Left installer app, assuming installation completed or cancelled")
                if self.status_callback:
                    try:
                        app_name = current_app_after if current_app_after and current_app_after.strip() else "应用市场"
                        self.status_callback("installation_completed", {
                            "app": app_name,
                            "status": "安装完成",
                            "message": "已离开安装器，安装可能已完成"
                        })
                    except Exception as e:
                        print(f"[Agent] Error in status callback: {e}")
                break
            
            # If screenshot hasn't changed for a while, might be stuck
            if consecutive_same_screenshots > 20:  # 60 seconds without change
                print(f"[Agent] Screenshot unchanged for {consecutive_same_screenshots * check_interval}s, installation might be stuck")
                # Continue waiting, but log the issue
            
            # Report progress every 10 seconds (fallback if AI analysis fails)
            if waited % 10 == 0 and not installation_status:
                status_message = f"等待安装完成... ({waited}s/{max_wait_time}s)"
                if status_message != last_status_message:
                    print(f"[Agent] {status_message}")
                    if self.status_callback:
                        try:
                            app_name = current_app if current_app and current_app.strip() else "应用市场"
                            self.status_callback("installation_progress", {
                                "app": app_name,
                                "status": "安装中",
                                "message": status_message or "等待安装完成...",
                                "progress": min(waited / max_wait_time, 0.95)  # Max 95% until complete
                            })
                        except Exception as e:
                            print(f"[Agent] Error in status callback: {e}")
                    last_status_message = status_message
        
        if waited >= max_wait_time:
            print(f"[Agent] Timeout waiting for installation to complete")
            if self.status_callback:
                try:
                    app_name = current_app if current_app and current_app.strip() else "应用市场"
                    self.status_callback("installation_timeout", {
                        "app": app_name,
                        "status": "安装超时",
                        "message": f"等待安装超时 ({max_wait_time}s)"
                    })
                except Exception as e:
                    print(f"[Agent] Error in status callback: {e}")

    def _execute_step(
        self, user_prompt: str | None = None, is_first: bool = False, on_token: Callable[[str], None] = None
    ) -> StepResult:
        """Execute a single step of the agent loop."""
        self._step_count += 1

        # Capture current screen state
        device_factory = get_device_factory()
        
        # Check for ongoing installations and wait if needed
        self._check_and_wait_for_installations(device_factory)
        
        screenshot = device_factory.get_screenshot(self.agent_config.device_id)
        current_app = device_factory.get_current_app(
            self.agent_config.device_id, 
            installed_apps=self.agent_config.installed_apps
        )
        
        # Get actual screen size for coordinate conversion
        # IMPORTANT: AI model sees the screenshot (which may be resized) and gives coordinates
        # relative to the screenshot it sees using a 0-999 scale. We need to convert these
        # coordinates to actual screen coordinates.
        #
        # The conversion works as follows:
        # 1. AI gives relative coord [x_rel, y_rel] where 0-999 maps to the screenshot dimensions it sees
        # 2. We convert to actual screen coordinates using actual screen dimensions
        # 3. This works because the relative coordinate system (0-999) is proportional
        
        # Get actual screen size (for coordinate conversion)
        actual_screen_width = screenshot.original_width if screenshot.original_width else screenshot.width
        actual_screen_height = screenshot.original_height if screenshot.original_height else screenshot.height
        
        # Try to get actual screen size from device if available (most accurate)
        if hasattr(device_factory.module, 'get_screen_size'):
            try:
                screen_w, screen_h = device_factory.module.get_screen_size(self.agent_config.device_id)
                actual_screen_width = screen_w
                actual_screen_height = screen_h
            except Exception:
                pass  # Fall back to screenshot dimensions

        # Build messages
        if is_first:
            self._context.append(
                MessageBuilder.create_system_message(self.agent_config.system_prompt)
            )

            screen_info = MessageBuilder.build_screen_info(
                current_app, installed_apps=self.agent_config.installed_apps
            )
            # Add screenshot dimensions to help AI understand coordinate system
            screenshot_info = f"\n** Screenshot Dimensions **\nWidth: {screenshot.width}px, Height: {screenshot.height}px"
            
            # Add recordings info if available
            recordings_info_text = ""
            if hasattr(self.agent_config, 'available_recordings') and self.agent_config.available_recordings:
                recordings_info_text = "\n" + MessageBuilder.build_recordings_info(self.agent_config.available_recordings)
            
            text_content = f"{user_prompt}\n\n{screen_info}{screenshot_info}{recordings_info_text}"

            self._context.append(
                MessageBuilder.create_user_message(
                    text=text_content, image_base64=screenshot.base64_data
                )
            )
        else:
            screen_info = MessageBuilder.build_screen_info(
                current_app, installed_apps=self.agent_config.installed_apps
            )
            # Inject result message from previous step if available
            result_msg_str = ""
            if len(self._context) > 0 and self._context[-1].get("role") == "assistant":
                 # Check if we have a result message stored somewhere? 
                 # Actually, we can just use the 'message' from StepResult, but we are inside _execute_step.
                 # We don't have access to the *previous* result easily unless we store it.
                 # But wait, the loop in run() or step() calls _execute_step.
                 # Let's modify _execute_step to accept an optional 'previous_result_message'.
                 # OR, better: The Model sees its own output <answer>action</answer>.
                 # If the action failed or had a result message (like "User input: 123456"), we MUST tell the model.
                 pass

            # We need to pass the result message to the prompt.
            # The cleanest way is to append it to the text content.
            
            # Since we can't easily change the method signature of _execute_step without breaking things or managing state,
            # let's assume we want to pass "system feedback" about the last action.
            # But here we are building the User message for the CURRENT step.
            
            # Let's change how we call _execute_step in the loop?
            # No, let's store `last_action_result` in `self`.
            
            additional_info = ""
            if hasattr(self, '_last_action_result_message') and self._last_action_result_message:
                additional_info = f"\n\n** Last Action Result **\n{self._last_action_result_message}"
                self._last_action_result_message = None # Clear it

            # Add screenshot dimensions to help AI understand coordinate system
            screenshot_info = f"\n** Screenshot Dimensions **\nWidth: {screenshot.width}px, Height: {screenshot.height}px"
            text_content = f"** Screen Info **\n\n{screen_info}{additional_info}{screenshot_info}"

            # Debug: Check screenshot data before creating message
            if hasattr(self.model_client, 'is_vl_model') and self.model_client.is_vl_model:
                print(f"[Agent] Screenshot base64_data length: {len(screenshot.base64_data) if screenshot.base64_data else 0}")
                print(f"[Agent] Screenshot dimensions: {screenshot.width}x{screenshot.height}")

            self._context.append(
                MessageBuilder.create_user_message(
                    text=text_content, image_base64=screenshot.base64_data
                )
            )

        # Get model response
        try:
            msgs = get_messages(self.agent_config.lang)
            print("\n" + "=" * 50)
            print(f"💭 {msgs['thinking']}:")
            print("-" * 50)
            response = self.model_client.request(self._context, on_token=on_token)
        except Exception as e:
            if self.agent_config.verbose:
                traceback.print_exc()
            return StepResult(
                success=False,
                finished=True,
                action=None,
                thinking="",
                message=f"Model error: {e}",
            )

        # Parse action from response
        try:
            # Check if action is empty or None
            if not response.action or response.action.strip() == "":
                if self.agent_config.verbose:
                    print(f"Warning: Model returned empty action, treating as finish")
                action = finish(message="模型返回了空响应，任务已结束")
            else:
                action = parse_action(response.action)
        except ValueError as e:
            if self.agent_config.verbose:
                print(f"Error parsing action: {e}")
                traceback.print_exc()
            # If parsing fails, try to use the raw action as a finish message
            action_message = response.action if response.action else "无法解析模型响应"
            action = finish(message=f"解析动作失败: {action_message}")
        
        # CRITICAL: Add thinking to action dict for sensitive operation detection
        # This allows ActionHandler to check AI's reasoning even if current_app detection fails
        if hasattr(response, 'thinking') and response.thinking:
            action['thinking'] = response.thinking

        if self.agent_config.verbose:
            # Print thinking process
            print("-" * 50)
            print(f"🎯 {msgs['action']}:")
            print(json.dumps(action, ensure_ascii=False, indent=2))
            print("=" * 50 + "\n")

        # Remove image from context to save space
        self._context[-1] = MessageBuilder.remove_images_from_message(self._context[-1])

        # Check if this action should be retried
        action_type = action.get("_metadata")
        action_name = action.get("action")
        
        # Skip retry logic for finish actions and certain action types
        # Note: Type actions need special handling - they may report success but fail silently
        should_check_retry = (
            action_type == "do" and 
            action_name not in ["Wait", "Note", "Call_API", "Take_over"] and
            action_name is not None
        )
        
        # For Type actions, we need stricter validation since they may fail silently
        # Type actions can report success but the text might not actually be entered
        is_type_action = action_name in ["Type", "Type_Name"]
        
        # Create action signature for retry tracking
        action_signature = json.dumps(action, sort_keys=True) if should_check_retry else None
        
        # Get retry count for this action
        max_retries = 3
        
        # Execute action with retry logic
        result = None
        action_effective = False
        
        for attempt in range(max_retries + 1):
            # Check if this is the last attempt
            is_last_attempt = (attempt >= max_retries)
            
            # ============================================================
            # STEP 1: Capture ORIGINAL screenshot BEFORE action (for comparison)
            # ============================================================
            # This screenshot is used ONLY for comparison, NOT for annotation
            # The annotation uses the step-start screenshot (stored in 'screenshot' variable)
            screenshot_before = None
            if should_check_retry:
                screenshot_before = device_factory.get_screenshot(self.agent_config.device_id)
                # This is guaranteed to be an ORIGINAL screenshot (not annotated)
                if self.agent_config.verbose:
                    print(f"[Retry] Step 1: Captured ORIGINAL screenshot_before for comparison (attempt {attempt + 1}/{max_retries + 1})")
            
            # ============================================================
            # STEP 2: Execute action (may generate annotated_screenshot for display)
            # ============================================================
            # For Tap actions: 
            #   - We pass the step-start screenshot for annotation (to generate marked image for UI)
            #   - The annotated_screenshot is stored in result.annotated_screenshot (for UI display only)
            #   - screenshot_before (captured above) is NOT used for annotation, only for comparison
            try:
                action_name = action.get("action")
                if action_name == "Tap" and screenshot.base64_data:
                    # Pass step-start screenshot for annotation (generates marked image for UI)
                    # screenshot_before is NOT passed here - it's only for comparison
                    result = self.action_handler.execute(
                        action, actual_screen_width, actual_screen_height, current_app=current_app,
                        screenshot_base64=screenshot.base64_data,  # Step-start screenshot for annotation
                        screenshot_width=screenshot.width,
                        screenshot_height=screenshot.height
                    )
                    # result.annotated_screenshot contains the marked image (for UI display only)
                else:
                    result = self.action_handler.execute(
                        action, actual_screen_width, actual_screen_height, current_app=current_app
                    )
                # Store message for next step context if it's significant (not just None)
                if result.message:
                    self._last_action_result_message = result.message
            except Exception as e:
                if self.agent_config.verbose:
                    traceback.print_exc()
                result = self.action_handler.execute(
                    finish(message=str(e)), actual_screen_width, actual_screen_height
                )
            
            # If action failed immediately and not retryable, don't retry
            if not result.success and not should_check_retry:
                break
            
            # ============================================================
            # STEP 3: Check if action was effective by comparing ORIGINAL screenshots
            # ============================================================
            if should_check_retry and screenshot_before:
                # If action reported failure, consider it ineffective regardless of screenshot
                if not result.success:
                    action_effective = False
                    if self.agent_config.verbose:
                        print(f"[Retry] Action '{action_name}' failed (attempt {attempt + 1}/{max_retries + 1}): {result.message}")
                else:
                    # For Type actions, wait longer to ensure UI updates
                    # Type actions may report success but fail silently (e.g., input field not focused)
                    wait_time = 1.0 if is_type_action else 0.5
                    import time
                    time.sleep(wait_time)
                    
                    # ============================================================
                    # STEP 4: Capture ORIGINAL screenshot AFTER action (for comparison)
                    # ============================================================
                    # This is a fresh capture from the device, guaranteed to be ORIGINAL (not annotated)
                    screenshot_after = device_factory.get_screenshot(self.agent_config.device_id)
                    if self.agent_config.verbose:
                        print(f"[Retry] Step 4: Captured ORIGINAL screenshot_after for comparison (attempt {attempt + 1}/{max_retries + 1})")
                        # Verify we're comparing original screenshots (not annotated)
                        if hasattr(result, 'annotated_screenshot') and result.annotated_screenshot:
                            print(f"[Retry] Note: annotated_screenshot exists in result (for UI display) but is NOT used for comparison")
                            print(f"[Retry] Comparison: screenshot_before (ORIGINAL) vs screenshot_after (ORIGINAL)")
                    
                    # ============================================================
                    # STEP 5: Compare ORIGINAL screenshots to detect changes
                    # ============================================================
                    # CRITICAL: We compare ORIGINAL screenshots (before and after), NOT annotated versions
                    # - screenshot_before: ORIGINAL screenshot captured before action
                    # - screenshot_after: ORIGINAL screenshot captured after action
                    # - annotated_screenshot: Only used for UI display, NOT for comparison
                    # If screenshots are identical, the action had no effect on the screen
                    if screenshot_before.base64_data and screenshot_after.base64_data:
                        # Simple comparison: if screenshots are identical, action may not have been effective
                        if screenshot_before.base64_data == screenshot_after.base64_data:
                            # Screenshot unchanged - action definitely not effective
                            action_effective = False
                            if self.agent_config.verbose:
                                print(f"[Retry] Action '{action_name}' did not change screen (attempt {attempt + 1}/{max_retries + 1})")
                                if is_type_action:
                                    print(f"[Retry] Type action likely failed - text was not entered (screenshot unchanged)")
                                    print(f"[Retry] Possible reasons:")
                                    print(f"[Retry]   1. Input field was not focused (AI should have clicked the input field first)")
                                    print(f"[Retry]   2. Input field is not editable or is disabled")
                                    print(f"[Retry]   3. ADB keyboard was not properly activated")
                                    print(f"[Retry]   4. Input field is hidden or covered by another element")
                            
                            # For Type actions, if ADB input failed on first attempt, immediately try visual click method
                            if is_type_action and attempt == 0 and not action_effective:
                                if self.agent_config.verbose:
                                    print(f"[Type Visual Click] ADB input failed on first attempt, immediately trying visual click method...")
                                try:
                                    visual_click_result = self._type_with_visual_clicks(
                                        action.get("text", ""),
                                        screenshot,
                                        actual_screen_width,
                                        actual_screen_height
                                    )
                                    if visual_click_result and visual_click_result.get("success"):
                                        # Visual click method succeeded
                                        if self.agent_config.verbose:
                                            print(f"[Type Visual Click] Successfully input text using visual clicks!")
                                        action_effective = True
                                        if result:
                                            result.success = True
                                            result.message = visual_click_result.get("message", "通过视觉点击方式成功输入文本")
                                        else:
                                            result = ActionResult(True, False, message=visual_click_result.get("message", "通过视觉点击方式成功输入文本"))
                                        # Reset retry count since visual click method succeeded
                                        if action_signature in self._action_retry_counts:
                                            del self._action_retry_counts[action_signature]
                                        break  # Exit retry loop since visual click succeeded
                                    else:
                                        if self.agent_config.verbose:
                                            print(f"[Type Visual Click] Visual click method also failed: {visual_click_result.get('message', 'Unknown error') if visual_click_result else 'No result'}")
                                        # Continue with retry loop for ADB
                                except Exception as e:
                                    if self.agent_config.verbose:
                                        print(f"[Type Visual Click] Error during visual click input: {e}")
                                        traceback.print_exc()
                                    # Continue with retry loop for ADB
                        else:
                            # Screenshot changed - but for Type actions, we need to be more careful
                            # Type actions should cause visible changes (text appears in input field)
                            if is_type_action:
                                # For Type actions, screenshot change is a good sign but not definitive
                                # We'll assume it worked, but if it fails again, we'll retry
                                action_effective = True
                                if self.agent_config.verbose and attempt > 0:
                                    print(f"[Retry] Type action '{action_name}' succeeded on attempt {attempt + 1} (screenshot changed)")
                            else:
                                # For other actions, screenshot change is a good sign
                                action_effective = True
                                if self.agent_config.verbose and attempt > 0:
                                    print(f"[Retry] Action '{action_name}' succeeded on attempt {attempt + 1}")
                            
                            if action_effective:
                                # Reset retry count for this action since it succeeded
                                if action_signature in self._action_retry_counts:
                                    del self._action_retry_counts[action_signature]
                                break
                    else:
                        # Cannot compare screenshots
                        if is_type_action:
                            # For Type actions, if we can't verify, be conservative and assume it might have failed
                            # This is safer than assuming success, as Type actions can fail silently
                            action_effective = False
                            if self.agent_config.verbose:
                                print(f"[Retry] Cannot verify Type action effectiveness (screenshot comparison failed) - assuming ineffective for safety")
                        else:
                            # For other actions, assume effective if result.success
                            action_effective = result.success
                            if result.success:
                                # Reset retry count for this action since it succeeded
                                if action_signature in self._action_retry_counts:
                                    del self._action_retry_counts[action_signature]
                                break
            elif should_check_retry:
                # No screenshot before - we cannot verify effectiveness directly
                # For safety, if action failed, consider it ineffective
                # If action succeeded but we can't verify, we should still check with screenshot
                # So we'll try to get a screenshot after action to verify
                if not result.success:
                    action_effective = False
                else:
                    # Action reported success, but we need to verify with screenshot
                    # Wait a bit and get screenshot to verify
                    import time
                    time.sleep(0.5)
                    screenshot_after = device_factory.get_screenshot(self.agent_config.device_id)
                    
                    # Try to compare with the screenshot we captured at the start of this step
                    # (which is stored in the 'screenshot' variable at the top of _execute_step)
                    if screenshot.base64_data and screenshot_after.base64_data:
                        if screenshot.base64_data == screenshot_after.base64_data:
                            # Page didn't change - action was ineffective
                            action_effective = False
                            if self.agent_config.verbose:
                                print(f"[Retry] Action '{action_name}' did not change screen (no screenshot_before, but compared with step start screenshot)")
                        else:
                            # Page changed - action was effective
                            action_effective = True
                            if action_signature in self._action_retry_counts:
                                del self._action_retry_counts[action_signature]
                            break
                    else:
                        # Cannot verify - be conservative for Type actions, optimistic for others
                        if is_type_action:
                            action_effective = False
                            if self.agent_config.verbose:
                                print(f"[Retry] Cannot verify Type action effectiveness - assuming ineffective for safety")
                        else:
                            # For other actions, assume effective if result.success
                            action_effective = True
                            if action_signature in self._action_retry_counts:
                                del self._action_retry_counts[action_signature]
                            break
            
            # If action was effective, break
            if action_effective:
                break
            
            # If we're here, action was ineffective
            # Update retry count
            self._action_retry_counts[action_signature] = attempt + 1
            
            # If this is the last attempt, don't retry, let the loop end naturally
            if is_last_attempt:
                # Last attempt failed, mark for user guidance
                if self.agent_config.verbose:
                    print(f"[Retry] Action '{action_name}' failed after {max_retries + 1} attempts, will request user guidance")
            else:
                # Not last attempt, retry
                if self.agent_config.verbose:
                    print(f"[Retry] Retrying action '{action_name}' (attempt {attempt + 2}/{max_retries + 1})")
                # Wait a bit before retry
                import time
                time.sleep(0.5)
        
        # Note: Visual click fallback for Type actions is now handled immediately after first ADB attempt fails
        # (see code around line 430-470 in the retry loop above)
        # This ensures we try visual click as soon as ADB fails, rather than retrying ADB multiple times
        
        # If action failed after max retries, request user guidance
        # Trigger if: (1) we've exhausted all retries, AND (2) action was ineffective (page didn't change)
        # IMPORTANT: Even if result.success is True, if the page didn't change (action_effective=False),
        # it means the action was ineffective and we need user guidance
        should_request_guidance = (
            should_check_retry and 
            not action_effective  # Page didn't change after action = action was ineffective
        )
        
        if self.agent_config.verbose:
            if should_request_guidance:
                print(f"[Retry] Action '{action_name}' was ineffective after {max_retries + 1} attempts (page didn't change)")
                print(f"[Retry] action_effective={action_effective}, result.success={result.success if result else None}")
                print(f"[Retry] should_check_retry={should_check_retry}, click_annotation_callback={'available' if self.click_annotation_callback else 'None'}")
                print(f"[Retry] Requesting user guidance for action '{action_name}'")
            else:
                print(f"[Retry] Not requesting guidance: should_check_retry={should_check_retry}, action_effective={action_effective}, result.success={result.success if result else None}")
                if should_check_retry and action_effective:
                    print(f"[Retry] Action was marked as effective, so no guidance needed")
                elif not should_check_retry:
                    print(f"[Retry] Action type does not require retry check")
        
        if should_request_guidance:
            if self.click_annotation_callback:
                # Request user to guide the operation
                guidance_message = (
                    f"操作 '{action_name}' 在重试 {max_retries} 次后仍然无效。"
                    f"请查看当前屏幕截图，标注应该点击的位置或描述正确的操作步骤。"
                )
                if self.agent_config.verbose:
                    print(f"[Retry] Calling click_annotation_callback for user guidance...")
                try:
                    annotation = self.click_annotation_callback(guidance_message)
                    if annotation and annotation.get("x") is not None and annotation.get("y") is not None:
                        # User provided click annotation - execute it
                        x = annotation["x"]
                        y = annotation["y"]
                        description = annotation.get("description", "")
                        
                        device_factory.tap(x, y, self.agent_config.device_id)
                        import time
                        from phone_agent.config.timing import TIMING_CONFIG
                        time.sleep(TIMING_CONFIG.device.default_tap_delay)
                        
                        result_message = f"根据用户指导点击了位置 ({x}, {y})"
                        if description:
                            result_message += f": {description}"
                        
                        if result:
                            result.message = result_message
                            result.success = True
                        else:
                            result = ActionResult(True, False, message=result_message)
                        
                        # Reset retry count for this action since user guided it
                        if action_signature in self._action_retry_counts:
                            del self._action_retry_counts[action_signature]
                except Exception as e:
                    if self.agent_config.verbose:
                        print(f"[Retry] Error requesting user guidance: {e}")
                        traceback.print_exc()
                    # Fall through to return the failed result
            else:
                if self.agent_config.verbose:
                    print(f"[Retry] WARNING: click_annotation_callback is None, cannot request user guidance!")
                    print(f"[Retry] This should not happen - check if callback was properly passed to PhoneAgent")

        # Add assistant response to context
        self._context.append(
            MessageBuilder.create_assistant_message(
                f"<think>{response.thinking}</think><answer>{response.action}</answer>"
            )
        )

        # Check if finished
        finished = action.get("_metadata") == "finish" or result.should_finish

        if finished and self.agent_config.verbose:
            msgs = get_messages(self.agent_config.lang)
            print("\n" + "🎉 " + "=" * 48)
            print(
                f"✅ {msgs['task_completed']}: {result.message or action.get('message', msgs['done'])}"
            )
            print("=" * 50 + "\n")

        return StepResult(
            success=result.success,
            finished=finished,
            action=action,
            thinking=response.thinking,
            message=result.message or action.get("message"),
            annotated_screenshot=result.annotated_screenshot if result else None
        )

    @property
    def context(self) -> list[dict[str, Any]]:
        """Get the current conversation context."""
        return self._context.copy()

    @property
    def step_count(self) -> int:
        """Get the current step count."""
        return self._step_count
    
    def _type_with_visual_clicks(
        self, 
        text: str, 
        screenshot: Any,
        actual_screen_width: int,
        actual_screen_height: int
    ) -> dict[str, Any] | None:
        """
        Type action using visual clicks: identify keyboard keys with AI and click them to input text.
        
        When ADB input fails, this method uses AI vision to:
        1. Identify the input field position
        2. Click the input field to focus it
        3. For each character in the text, identify the keyboard key position using AI
        4. Click each key sequentially to input the text
        
        Args:
            text: Text to input
            screenshot: Current screenshot
            actual_screen_width: Actual screen width
            actual_screen_height: Actual screen height
            
        Returns:
            Dict with 'success' (bool) and 'message' (str), or None if failed
        """
        if not text:
            return {"success": False, "message": "Empty text to input"}
        
        device_factory = get_device_factory()
        import time
        from phone_agent.config.timing import TIMING_CONFIG
        
        try:
            # Step 1: Identify input field position using AI
            if self.agent_config.verbose:
                print(f"[Type Visual Click] Step 1: Identifying input field position using AI...")
            
            input_field_prompt = (
                "请查看当前屏幕截图，识别出文本输入框的位置。"
                "输入框通常是可编辑的文本框，可能显示占位符文本或光标。"
                "请返回输入框的中心位置坐标，格式为：do(action=\"Tap\", element=[x,y])"
                "其中 x 和 y 是相对于截图尺寸的坐标（0-999范围）。"
                f"截图尺寸：宽度 {screenshot.width}px，高度 {screenshot.height}px。"
            )
            
            # Create a temporary context for input field identification
            temp_context = [
                MessageBuilder.create_system_message(
                    "你是一个UI元素识别助手。请根据屏幕截图识别输入框位置，并返回点击坐标。"
                ),
                MessageBuilder.create_user_message(
                    input_field_prompt,
                    image_base64=screenshot.base64_data,
                    image_format="jpeg"
                )
            ]
            
            input_field_response = self.model_client.request(temp_context)
            input_field_action_str = input_field_response.action
            
            # Parse the Tap action
            try:
                input_field_action = parse_action(input_field_action_str)
                if input_field_action.get("_metadata") != "do" or input_field_action.get("action") != "Tap":
                    return {"success": False, "message": f"AI未能识别输入框位置，返回：{input_field_action_str}"}
                
                input_element = input_field_action.get("element")
                if not input_element or len(input_element) != 2:
                    return {"success": False, "message": f"AI返回的输入框坐标格式错误：{input_element}"}
                
                # Convert relative coordinates to absolute
                input_x_rel, input_y_rel = input_element
                input_x = int(input_x_rel * actual_screen_width / 1000)
                input_y = int(input_y_rel * actual_screen_height / 1000)
                
                if self.agent_config.verbose:
                    print(f"[Type Visual Click] Input field position: ({input_x}, {input_y})")
                
                # Step 2: Click the input field to focus it
                if self.agent_config.verbose:
                    print(f"[Type Visual Click] Step 2: Clicking input field to focus it...")
                device_factory.tap(input_x, input_y, self.agent_config.device_id)
                time.sleep(TIMING_CONFIG.device.default_tap_delay + 0.5)  # Wait for keyboard to appear
                
                # Step 3: For each character, identify and click the keyboard key
                if self.agent_config.verbose:
                    print(f"[Type Visual Click] Step 3: Inputting text character by character using visual clicks...")
                
                for i, char in enumerate(text):
                    if self.agent_config.verbose:
                        print(f"[Type Visual Click] Inputting character {i+1}/{len(text)}: '{char}'")
                    
                    # Get current screenshot (keyboard should be visible now)
                    current_screenshot = device_factory.get_screenshot(self.agent_config.device_id)
                    
                    # Use AI to identify the keyboard key position for this character
                    keyboard_prompt = (
                        f"请查看当前屏幕截图，识别出键盘上字符 '{char}' 的位置。"
                        "键盘通常显示在屏幕底部。请返回该字符按键的中心位置坐标，格式为：do(action=\"Tap\", element=[x,y])"
                        "其中 x 和 y 是相对于截图尺寸的坐标（0-999范围）。"
                        f"截图尺寸：宽度 {current_screenshot.width}px，高度 {current_screenshot.height}px。"
                        "如果找不到该字符（例如特殊字符），请返回 finish(message=\"找不到字符\")"
                    )
                    
                    temp_context = [
                        MessageBuilder.create_system_message(
                            "你是一个UI元素识别助手。请根据屏幕截图识别键盘按键位置，并返回点击坐标。"
                        ),
                        MessageBuilder.create_user_message(
                            keyboard_prompt,
                            image_base64=current_screenshot.base64_data,
                            image_format="jpeg"
                        )
                    ]
                    
                    keyboard_response = self.model_client.request(temp_context)
                    keyboard_action_str = keyboard_response.action
                    
                    # Parse the Tap action
                    try:
                        keyboard_action = parse_action(keyboard_action_str)
                        if keyboard_action.get("_metadata") == "finish":
                            return {"success": False, "message": f"AI无法找到字符 '{char}' 的键盘位置"}
                        
                        if keyboard_action.get("_metadata") != "do" or keyboard_action.get("action") != "Tap":
                            return {"success": False, "message": f"AI未能识别字符 '{char}' 的键盘位置，返回：{keyboard_action_str}"}
                        
                        key_element = keyboard_action.get("element")
                        if not key_element or len(key_element) != 2:
                            return {"success": False, "message": f"AI返回的字符 '{char}' 的键盘坐标格式错误：{key_element}"}
                        
                        # Convert relative coordinates to absolute
                        key_x_rel, key_y_rel = key_element
                        key_x = int(key_x_rel * actual_screen_width / 1000)
                        key_y = int(key_y_rel * actual_screen_height / 1000)
                        
                        if self.agent_config.verbose:
                            print(f"[Type Visual Click] Character '{char}' key position: ({key_x}, {key_y})")
                        
                        # Click the keyboard key
                        device_factory.tap(key_x, key_y, self.agent_config.device_id)
                        time.sleep(0.2)  # Wait between key presses
                        
                    except Exception as e:
                        if self.agent_config.verbose:
                            print(f"[Type Visual Click] Error identifying/clicking character '{char}': {e}")
                        return {"success": False, "message": f"处理字符 '{char}' 时出错：{e}"}
                
                if self.agent_config.verbose:
                    print(f"[Type Visual Click] Successfully input all {len(text)} characters using visual clicks")
                
                return {"success": True, "message": f"通过视觉点击方式成功输入了 {len(text)} 个字符"}
                
            except Exception as e:
                if self.agent_config.verbose:
                    print(f"[Type Visual Click] Error parsing input field action: {e}")
                return {"success": False, "message": f"解析输入框位置时出错：{e}"}
                
        except Exception as e:
            if self.agent_config.verbose:
                print(f"[Type Visual Click] Error during visual click input: {e}")
                traceback.print_exc()
            return {"success": False, "message": f"视觉点击输入过程中出错：{e}"}
