"""Action handler for processing AI model outputs."""

import ast
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable

from phone_agent.config.timing import TIMING_CONFIG
from phone_agent.device_factory import get_device_factory
from phone_agent.utils.app_matcher import match_app_with_llm
from phone_agent.utils.image_annotation import annotate_click_position


@dataclass
class ActionResult:
    """Result of an action execution."""

    success: bool
    should_finish: bool
    message: str | None = None
    requires_confirmation: bool = False
    annotated_screenshot: str | None = None  # Screenshot with click position marked (for Tap actions)


class ActionHandler:
    """
    Handles execution of actions from AI model output.

    Args:
        device_id: Optional ADB device ID for multi-device setups.
        confirmation_callback: Optional callback for sensitive action confirmation.
            Should return True to proceed, False to cancel.
        takeover_callback: Optional callback for takeover requests (login, captcha).
    """

    def __init__(
        self,
        device_id: str | None = None,
        confirmation_callback: Callable[[str], bool] | None = None,
        takeover_callback: Callable[[str], None] | None = None,
        input_callback: Callable[[str], str] | None = None,
        click_annotation_callback: Callable[[str], dict] | None = None,
        model_client: Any = None,
        installed_apps: list[dict[str, Any]] | None = None,
        system_app_mappings: dict[str, list] | None = None,
        llm_prompt_template: str | None = None,
    ):
        self.device_id = device_id
        self.confirmation_callback = confirmation_callback or self._default_confirmation
        self.takeover_callback = takeover_callback or self._default_takeover
        self.input_callback = input_callback or self._default_input
        self.click_annotation_callback = click_annotation_callback
        self.model_client = model_client
        self.installed_apps = installed_apps
        self.system_app_mappings = system_app_mappings
        self.llm_prompt_template = llm_prompt_template

    def execute(
        self, action: dict[str, Any], screen_width: int, screen_height: int, current_app: str = None,
        screenshot_base64: str = None, screenshot_width: int = None, screenshot_height: int = None
    ) -> ActionResult:
        """
        Execute an action from the AI model.

        Args:
            action: The action dictionary from the model.
            screen_width: Current screen width in pixels.
            screen_height: Current screen height in pixels.
            current_app: Current app package name (optional).

        Returns:
            ActionResult indicating success and whether to finish.
        """
        action_type = action.get("_metadata")

        if action_type == "finish":
            return ActionResult(
                success=True, should_finish=True, message=action.get("message")
            )

        if action_type != "do":
            print(f"[ActionHandler] Warning: Invalid action type '{action_type}'. Action: {action}", flush=True)
            return ActionResult(
                success=False,
                should_finish=True,
                message=f"Unknown action type: {action_type}",
            )

        action_name = action.get("action")
        handler_method = self._get_handler(action_name)

        if handler_method is None:
            print(f"[ActionHandler] Warning: Unknown action '{action_name}'. Action: {action}", flush=True)
            return ActionResult(
                success=False,
                should_finish=False,
                message=f"Unknown action: {action_name}",
            )

        try:
            print(f"[ActionHandler] Executing action: {action_name} with params: {action}", flush=True)
            # Pass current_app to handler if it accepts it, otherwise backward compatible
            # Actually, let's just update internal handlers to accept **kwargs or explicitly
            # For simplicity, we can set self.current_app temporarily
            self.current_app = current_app 
            
            # For Tap actions, pass screenshot info for annotation
            if action_name == "Tap" and screenshot_base64 and screenshot_width and screenshot_height:
                # Check if handler accepts screenshot parameters
                import inspect
                sig = inspect.signature(handler_method)
                if 'screenshot_base64' in sig.parameters:
                    return handler_method(action, screen_width, screen_height, 
                                         screenshot_base64=screenshot_base64,
                                         screenshot_width=screenshot_width,
                                         screenshot_height=screenshot_height)
            
            return handler_method(action, screen_width, screen_height)
        except Exception as e:
            return ActionResult(
                success=False, should_finish=False, message=f"Action failed: {e}"
            )

    def _get_handler(self, action_name: str) -> Callable | None:
        """Get the handler method for an action."""
        handlers = {
            "Launch": self._handle_launch,
            "Tap": self._handle_tap,
            "Type": self._handle_type,
            "Type_Name": self._handle_type,
            "Swipe": self._handle_swipe,
            "Back": self._handle_back,
            "Home": self._handle_home,
            "Double Tap": self._handle_double_tap,
            "Long Press": self._handle_long_press,
            "Wait": self._handle_wait,
            "Take_over": self._handle_takeover,
            "Note": self._handle_note,
            "Call_API": self._handle_call_api,
            "Interact": self._handle_interact,
            "AskUserClick": self._handle_ask_user_click,
        }
        return handlers.get(action_name)

    def _convert_relative_to_absolute(
        self, element: list[int], screen_width: int, screen_height: int
    ) -> tuple[int, int]:
        """
        Convert relative coordinates (0-1000) to absolute pixels.
        
        Note: The AI model sees a screenshot (which may be resized) and gives coordinates
        relative to that screenshot. The screen_width/height passed here should be the
        actual screen dimensions, not the screenshot dimensions.
        
        The conversion formula:
        - AI gives relative coord [x_rel, y_rel] where 0-999 maps to screenshot dimensions
        - We convert to actual screen coordinates using the actual screen dimensions
        - This works because the relative coordinate system (0-999) is proportional
        """
        x = int(element[0] / 1000 * screen_width)
        y = int(element[1] / 1000 * screen_height)
        return x, y

    def _handle_launch(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle app launch action."""
        app_name = action.get("app")
        if not app_name:
            return ActionResult(False, False, "No app name specified")
        
        app_name = app_name.strip()
        
        # Extract action context from the action message if available
        action_context = action.get("message", "")
        # Also check if app_name contains action keywords
        action_keywords = ["发短信", "发信息", "打电话", "拨号", "联系人", "send", "sms", "call", "dial", "message"]
        if any(kw in app_name for kw in action_keywords):
            action_context = app_name
        
        # First, try to match app using LLM if model_client and installed_apps are available
        matched_package = None
        matched_app_name = None
        
        if self.model_client and self.installed_apps:
            try:
                match_result = match_app_with_llm(
                    app_name,
                    self.installed_apps,
                    self.model_client,
                    system_app_mappings=self.system_app_mappings,
                    llm_prompt_template=self.llm_prompt_template,
                    action_context=action_context if action_context else None
                )
                
                if match_result.get("installed", False):
                    matched_package = match_result.get("package_id")
                    matched_app_name = match_result.get("app_name")
                    print(f"[ActionHandler] LLM matched '{app_name}' to package '{matched_package}' (name: {matched_app_name})")
            except Exception as e:
                print(f"[ActionHandler] Error matching app with LLM: {e}")
        
        device_factory = get_device_factory()
        
        # If no match found and this is a system action, provide better error message
        if not matched_package:
            action_keywords = ["发短信", "发信息", "打电话", "拨号", "联系人", "send", "sms", "call", "dial", "message"]
            is_system_action = any(kw in app_name for kw in action_keywords)
            if is_system_action:
                # Check if we have installed_apps to provide more context
                if self.installed_apps:
                    # Try to find any SMS/MMS related apps in installed list
                    sms_keywords = ["短信", "信息", "消息", "mms", "messaging"]
                    found_apps = []
                    for app in self.installed_apps:
                        app_name_lower = (app.get("name", "") + " " + app.get("package", "")).lower()
                        if any(kw in app_name_lower for kw in sms_keywords):
                            found_apps.append(f"{app.get('name', '')} ({app.get('package', '')})")
                    
                    if found_apps:
                        return ActionResult(
                            False, 
                            True, 
                            f"设备上未找到短信应用,无法发送短信。但发现以下相关应用: {', '.join(found_apps[:3])}"
                        )
                
                return ActionResult(
                    False, 
                    True, 
                    f"设备上未找到短信应用,无法发送短信。请检查设备是否已安装短信应用，或尝试在应用市场中安装。"
                )
        
        # Try to launch with matched package if available, otherwise use original app_name
        launch_name = matched_package if matched_package else app_name
        success = device_factory.launch_app(launch_name, self.device_id)
        
        if success:
            time.sleep(TIMING_CONFIG.device.default_launch_delay)
            if matched_app_name and matched_app_name != app_name:
                return ActionResult(True, False, f"Launched '{matched_app_name}' (matched from '{app_name}')")
            return ActionResult(True, False)
            
        # App not found -> Potential Install
        # Check permission configuration BEFORE attempting installation
        # This ensures that EVERY app installation is checked against configuration
        if not self._check_sensitive_permission("install_app", f"安装应用: {app_name}"):
            return ActionResult(False, True, "用户拒绝了应用安装操作")

        # Permission granted, instruct LLM to proceed with installation
        return ActionResult(
            success=False, 
            should_finish=False, 
            message=f"App '{app_name}' is not installed. Permission to install is granted. Please proceed to install it using the application market."
        )

    def _check_sensitive_permission(self, permission_key: str, message: str) -> bool:
        """
        Check if a sensitive action is allowed by configuration.
        
        This method is called EVERY TIME a sensitive action is about to be executed.
        It checks the device's permission configuration:
        - If permission is enabled: automatically approves (returns True)
        - If permission is disabled: requests user confirmation via callback (returns True/False based on user response)
        
        Args:
            permission_key: The permission key (e.g., "install_app", "payment", "send_sms")
            message: Human-readable message describing the action
        
        Returns:
            True if action is allowed (auto-approved or user confirmed), False if user denied
        """
        if not self.confirmation_callback:
            # No callback means we can't check permissions - deny by default for safety
            print(f"[ActionHandler] No confirmation callback available, denying sensitive action: {message}")
            return False
        
        # Format message with permission key prefix for callback to parse
        # Format: "[PERMISSION:key] message"
        full_msg = f"[PERMISSION:{permission_key}] {message}"
        
        # Callback will:
        # 1. Parse permission key from message
        # 2. Check device permission configuration
        # 3. If enabled: auto-approve (return True)
        # 4. If disabled: request user confirmation (return True/False based on user response)
        return self.confirmation_callback(full_msg)

    def _handle_tap(self, action: dict, width: int, height: int, screenshot_base64: str = None, 
                    screenshot_width: int = None, screenshot_height: int = None) -> ActionResult:
        """Handle tap action."""
        element = action.get("element")
        if not element:
            return ActionResult(False, False, "No element coordinates")

        x, y = self._convert_relative_to_absolute(element, width, height)

        # Sensitive Action Check
        current = getattr(self, 'current_app', '') or ''
        current = current.lower()
        
        # Install App Check - Only check permission if explicitly installing
        # Check if we're in an app store/market AND the action message indicates installation
        installer_keywords = ["market", "store", "installer", "应用市场", "应用商店", "play store", "app store"]
        is_in_installer = any(kw in current for kw in installer_keywords)
        
        if is_in_installer:
            # Check if this is an installation action by examining the action message
            action_message = action.get("message", "").lower() if isinstance(action.get("message"), str) else ""
            install_keywords = ["安装", "install", "下载", "download", "获取", "get app"]
            is_install_action = any(kw in action_message for kw in install_keywords)
            
            # Only check permission if this is explicitly an installation action
            if is_install_action:
                if not self._check_sensitive_permission("install_app", "在应用市场中执行安装操作"):
                    print(f"[Tap Action] Permission denied for app installation in market")
                    return ActionResult(False, True, "用户拒绝了应用安装操作")
        
        # Payment Check
        if any(app in current for app in ['alipay', 'wallet', 'pay']):
             if not self._check_sensitive_permission("payment", "Perform payment operation"):
                 return ActionResult(False, True, "User denied payment operation")
        
        # Make Call Check
        if any(app in current for app in ['dialer', 'contact', 'phone']):
             # Heuristic: Tapping call button (usually green or specific icon) is hard to know without icon detection
             # But we can be conservative
             if not self._check_sensitive_permission("make_call", "Make phone call"):
                 return ActionResult(False, True, "User denied phone call")

        # Annotate screenshot with click position before executing tap
        # IMPORTANT: x, y are in actual screen coordinates (after conversion from AI's relative coords)
        # screenshot_width/height are the dimensions of the screenshot that AI saw (may be resized)
        # width/height are the actual screen dimensions used for coordinate conversion
        annotated_screenshot = None
        if screenshot_base64 and screenshot_width and screenshot_height:
            try:
                # Debug: print coordinate info
                if hasattr(self, 'device_id') and self.device_id:
                    print(f"[Tap Annotation] Screen coords: ({x}, {y}), Screenshot size: {screenshot_width}x{screenshot_height}, Screen size: {width}x{height}")
                
                annotated_screenshot = annotate_click_position(
                    screenshot_base64=screenshot_base64,
                    x=x,  # Actual screen X coordinate
                    y=y,  # Actual screen Y coordinate
                    screenshot_width=screenshot_width,  # Screenshot width (AI saw this)
                    screenshot_height=screenshot_height,  # Screenshot height (AI saw this)
                    actual_screen_width=width,  # Actual screen width
                    actual_screen_height=height  # Actual screen height
                )
            except Exception as e:
                print(f"Error annotating click position: {e}")
                import traceback
                traceback.print_exc()

        device_factory = get_device_factory()
        device_factory.tap(x, y, self.device_id)
        time.sleep(TIMING_CONFIG.device.default_tap_delay)
        return ActionResult(True, False, annotated_screenshot=annotated_screenshot)

    def _handle_type(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle text input action."""
        text = action.get("text", "")
        
        print(f"[Type Action] Attempting to type text: '{text}'", flush=True)

        # Sensitive Action Check - Check permissions BEFORE typing text
        # This ensures that EVERY sensitive text input is checked against configuration
        current = getattr(self, 'current_app', '') or ''
        current = current.lower()
        
        # WeChat Reply Check - Check if we're in WeChat
        if 'tencent.mm' in current or 'wechat' in current:
            # Check permission configuration - will auto-approve if enabled, or request user confirmation if disabled
            if not self._check_sensitive_permission("wechat_reply", f"回复微信消息: {text[:50]}..."):
                print(f"[Type Action] Permission denied for WeChat reply", flush=True)
                return ActionResult(False, True, "用户拒绝了微信回复操作")

        # Send SMS Check - Check if we're in SMS/messaging app
        if any(app in current for app in ['mms', 'messaging', 'sms']):
            # Check permission configuration - will auto-approve if enabled, or request user confirmation if disabled
            if not self._check_sensitive_permission("send_sms", f"发送短信: {text[:50]}..."):
                print(f"[Type Action] Permission denied for SMS", flush=True)
                return ActionResult(False, True, "用户拒绝了发送短信操作")

        device_factory = get_device_factory()

        # Check if input field is focused (by checking if keyboard is visible)
        # This is a heuristic - we can't directly check focus, but we can check if keyboard is shown
        print(f"[Type Action Debug] Checking input field focus state...", flush=True)
        try:
            from phone_agent.adb.device import get_current_app
            current_app_info = get_current_app(self.device_id, installed_apps=None)
            print(f"[Type Action Debug] Current app: {current_app_info}", flush=True)
        except Exception as e:
            print(f"[Type Action Debug] Could not get current app: {e}", flush=True)

        # Switch to ADB keyboard
        print(f"[Type Action] Switching to ADB keyboard...", flush=True)
        original_ime = device_factory.detect_and_set_adb_keyboard(self.device_id)
        print(f"[Type Action] Original IME: {original_ime}, ADB keyboard activated", flush=True)
        time.sleep(TIMING_CONFIG.action.keyboard_switch_delay)

        # Clear existing text and type new text
        print(f"[Type Action] Clearing existing text...", flush=True)
        device_factory.clear_text(self.device_id)
        time.sleep(TIMING_CONFIG.action.text_clear_delay)

        # Handle multiline text by splitting on newlines
        print(f"[Type Action] Typing text: '{text}'...", flush=True)
        print(f"[Type Action Debug] Text details: length={len(text)}, contains_newline={chr(10) in text or chr(13) in text}", flush=True)
        device_factory.type_text(text, self.device_id)
        time.sleep(TIMING_CONFIG.action.text_input_delay)
        print(f"[Type Action] Text input completed", flush=True)

        # Restore original keyboard
        print(f"[Type Action] Restoring original keyboard: {original_ime}", flush=True)
        device_factory.restore_keyboard(original_ime, self.device_id)
        time.sleep(TIMING_CONFIG.action.keyboard_restore_delay)

        print(f"[Type Action] Type action completed successfully", flush=True)
        print(f"[Type Action Debug] Note: Success here means command executed, not that text was actually entered.", flush=True)
        print(f"[Type Action Debug] The system will verify by comparing screenshots before/after.", flush=True)
        return ActionResult(True, False)

    def _handle_swipe(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle swipe action."""
        start = action.get("start")
        end = action.get("end")

        if not start or not end:
            return ActionResult(False, False, "Missing swipe coordinates")

        start_x, start_y = self._convert_relative_to_absolute(start, width, height)
        end_x, end_y = self._convert_relative_to_absolute(end, width, height)

        device_factory = get_device_factory()
        device_factory.swipe(start_x, start_y, end_x, end_y, device_id=self.device_id)
        time.sleep(TIMING_CONFIG.device.default_swipe_delay)
        return ActionResult(True, False)

    def _handle_back(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle back button action."""
        device_factory = get_device_factory()
        device_factory.back(self.device_id)
        time.sleep(TIMING_CONFIG.device.default_back_delay)
        return ActionResult(True, False)

    def _handle_home(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle home button action."""
        device_factory = get_device_factory()
        device_factory.home(self.device_id)
        time.sleep(TIMING_CONFIG.device.default_home_delay)
        return ActionResult(True, False)

    def _handle_double_tap(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle double tap action."""
        element = action.get("element")
        if not element:
            return ActionResult(False, False, "No element coordinates")

        x, y = self._convert_relative_to_absolute(element, width, height)
        device_factory = get_device_factory()
        device_factory.double_tap(x, y, self.device_id)
        time.sleep(TIMING_CONFIG.device.default_double_tap_delay)
        return ActionResult(True, False)

    def _handle_long_press(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle long press action."""
        element = action.get("element")
        if not element:
            return ActionResult(False, False, "No element coordinates")

        x, y = self._convert_relative_to_absolute(element, width, height)
        device_factory = get_device_factory()
        device_factory.long_press(x, y, device_id=self.device_id)
        time.sleep(TIMING_CONFIG.device.default_long_press_delay)
        return ActionResult(True, False)

    def _handle_wait(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle wait action."""
        duration_str = action.get("duration", "1 seconds")
        try:
            duration = float(duration_str.replace("seconds", "").strip())
        except ValueError:
            duration = 1.0

        time.sleep(duration)
        return ActionResult(True, False)

    def _handle_takeover(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle takeover request (login, captcha, etc.)."""
        message = action.get("message", "User intervention required")
        self.takeover_callback(message)
        return ActionResult(True, False)

    def _handle_note(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle note action (placeholder for content recording)."""
        # This action is typically used for recording page content
        # Implementation depends on specific requirements
        return ActionResult(True, False)

    def _handle_call_api(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle API call action (placeholder for summarization)."""
        # This action is typically used for content summarization
        # Implementation depends on specific requirements
        return ActionResult(True, False)

    def _handle_interact(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle interaction request (user choice needed)."""
        # This action signals that user input is needed
        # Check if message is provided in action?
        # The prompt says: "Interact是当有多个满足条件的选项时而触发的交互操作，询问用户如何选择。"
        # We can try to extract a 'message' or 'question' from kwargs if available, or use default.
        # But 'do(action="Interact")' usually has no args.
        # Let's check if the model provided 'message'.
        message = action.get("message", "Please provide input or choice for the next step.")
        
        user_response = self.input_callback(message)
        return ActionResult(True, False, message=f"User input: {user_response}")
    
    def _handle_ask_user_click(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle request for user to annotate click position on screenshot."""
        if not self.click_annotation_callback:
            return ActionResult(False, False, "Click annotation callback not available")
        
        message = action.get("message", "Please click on the screen to indicate where to tap.")
        
        # Request user annotation
        annotation = self.click_annotation_callback(message)
        
        if annotation and annotation.get("x") and annotation.get("y"):
            # Execute the tap at annotated position
            x = annotation["x"]
            y = annotation["y"]
            description = annotation.get("description", "")
            
            device_factory = get_device_factory()
            device_factory.tap(x, y, self.device_id)
            time.sleep(TIMING_CONFIG.device.default_tap_delay)
            
            result_message = f"Tapped at user-annotated position ({x}, {y})"
            if description:
                result_message += f": {description}"
            
            return ActionResult(True, False, message=result_message)
        else:
            return ActionResult(False, False, "User did not provide click annotation")

    def _send_keyevent(self, keycode: str) -> None:
        """Send a keyevent to the device."""
        from phone_agent.device_factory import DeviceType, get_device_factory
        from phone_agent.hdc.connection import _run_hdc_command

        device_factory = get_device_factory()

        # Handle HDC devices with HarmonyOS-specific keyEvent command
        if device_factory.device_type == DeviceType.HDC:
            hdc_prefix = ["hdc", "-t", self.device_id] if self.device_id else ["hdc"]
            
            # Map common keycodes to HarmonyOS keyEvent codes
            # KEYCODE_ENTER (66) -> 2054 (HarmonyOS Enter key code)
            if keycode == "KEYCODE_ENTER" or keycode == "66":
                _run_hdc_command(
                    hdc_prefix + ["shell", "uitest", "uiInput", "keyEvent", "2054"],
                    capture_output=True,
                    text=True,
                )
            else:
                # For other keys, try to use the numeric code directly
                # If keycode is a string like "KEYCODE_ENTER", convert it
                try:
                    # Try to extract numeric code from string or use as-is
                    if keycode.startswith("KEYCODE_"):
                        # For now, only handle ENTER, other keys may need mapping
                        if "ENTER" in keycode:
                            _run_hdc_command(
                                hdc_prefix + ["shell", "uitest", "uiInput", "keyEvent", "2054"],
                                capture_output=True,
                                text=True,
                            )
                        else:
                            # Fallback to ADB-style command for unsupported keys
                            subprocess.run(
                                hdc_prefix + ["shell", "input", "keyevent", keycode],
                                capture_output=True,
                                text=True,
                            )
                    else:
                        # Assume it's a numeric code
                        _run_hdc_command(
                            hdc_prefix + ["shell", "uitest", "uiInput", "keyEvent", str(keycode)],
                            capture_output=True,
                            text=True,
                        )
                except Exception:
                    # Fallback to ADB-style command
                    subprocess.run(
                        hdc_prefix + ["shell", "input", "keyevent", keycode],
                        capture_output=True,
                        text=True,
                    )
        else:
            # ADB devices use standard input keyevent command
            cmd_prefix = ["adb", "-s", self.device_id] if self.device_id else ["adb"]
            subprocess.run(
                cmd_prefix + ["shell", "input", "keyevent", keycode],
                capture_output=True,
                text=True,
            )

    @staticmethod
    def _default_confirmation(message: str) -> bool:
        """Default confirmation callback using console input."""
        response = input(f"Sensitive operation: {message}\nConfirm? (Y/N): ")
        return response.upper() == "Y"

    @staticmethod
    def _default_takeover(message: str) -> None:
        """Default takeover callback using console input."""
        input(f"{message}\nPress Enter after completing manual operation...")

    @staticmethod
    def _default_input(message: str) -> str:
        """Default input callback using console input."""
        return input(f"{message}\nInput: ")


def parse_action(response: str) -> dict[str, Any]:
    """
    Parse action from model response.

    Args:
        response: Raw response string from the model.

    Returns:
        Parsed action dictionary.

    Raises:
        ValueError: If the response cannot be parsed.
    """
    print(f"Parsing action: {response}")
    try:
        response = response.strip()
        
        # Clean up XML tags if present
        if "</answer>" in response:
            response = response.split("</answer>")[0].strip()
            
        if response.startswith("do"):
            # Use AST parsing instead of eval for safety
            try:
                # Escape special characters (newlines, tabs, etc.) for valid Python syntax
                response = response.replace('\n', '\\n')
                response = response.replace('\r', '\\r')
                response = response.replace('\t', '\\t')

                tree = ast.parse(response, mode="eval")
                if not isinstance(tree.body, ast.Call):
                    raise ValueError("Expected a function call")

                call = tree.body
                # Extract keyword arguments safely
                action = {"_metadata": "do"}
                for keyword in call.keywords:
                    key = keyword.arg
                    value = ast.literal_eval(keyword.value)
                    action[key] = value

                return action
            except (SyntaxError, ValueError) as e:
                raise ValueError(f"Failed to parse do() action: {e}")

        elif response.startswith("finish"):
            action = {
                "_metadata": "finish",
                "message": response.replace("finish(message=", "")[1:-2],
            }
        elif not response or response.strip() == "":
            # Empty response - treat as finish with empty message
            action = {
                "_metadata": "finish",
                "message": "模型返回了空响应，任务已结束",
            }
        else:
            raise ValueError(f"Failed to parse action: {response}")
        return action
    except Exception as e:
        raise ValueError(f"Failed to parse action: {e}")


def do(**kwargs) -> dict[str, Any]:
    """Helper function for creating 'do' actions."""
    kwargs["_metadata"] = "do"
    return kwargs


def finish(**kwargs) -> dict[str, Any]:
    """Helper function for creating 'finish' actions."""
    kwargs["_metadata"] = "finish"
    return kwargs
