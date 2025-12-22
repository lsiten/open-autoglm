"""Service for executing recorded actions."""

import asyncio
import time
from typing import Tuple, Optional
from ..services.recording_manager import Recording, RecordedAction
from ..services.device_manager import device_manager
from phone_agent.device_factory import get_device_factory, set_device_type, DeviceType

async def execute_recording_actions(recording: Recording, device_id: str) -> Tuple[bool, str]:
    """
    Execute a recording's actions on a device.
    
    Args:
        recording: The recording to execute
        device_id: Target device ID
        
    Returns:
        (success, message) tuple
    """
    try:
        # Set device type
        if recording.device_type == "hdc":
            set_device_type(DeviceType.HDC)
        elif recording.device_type == "ios":
            set_device_type(DeviceType.IOS)
        else:
            set_device_type(DeviceType.ADB)
        
        factory = get_device_factory()
        
        # Execute actions in sequence
        last_timestamp = 0.0
        for i, action in enumerate(recording.actions):
            # Wait for the delay since last action
            delay = action.timestamp - last_timestamp
            if delay > 0:
                await asyncio.sleep(delay)
            
            # Execute the action
            action_type = action.action_type
            params = action.params
            
            try:
                if action_type == "tap":
                    factory.tap(params["x"], params["y"], device_id=device_id)
                elif action_type == "swipe":
                    factory.swipe(
                        params["x1"], params["y1"],
                        params["x2"], params["y2"],
                        duration_ms=params.get("duration", 500),
                        device_id=device_id
                    )
                elif action_type == "type":
                    factory.type_text(params["text"], device_id=device_id)
                elif action_type == "back":
                    factory.back(device_id=device_id)
                elif action_type == "home":
                    factory.home(device_id=device_id)
                elif action_type == "recent":
                    if hasattr(factory, "recent"):
                        factory.recent(device_id=device_id)
                    else:
                        print(f"Recent apps not supported on this device type")
                        continue
                elif action_type == "wait":
                    await asyncio.sleep(params.get("duration", 1.0))
                else:
                    print(f"Unknown action type: {action_type}")
                    continue
                
                # Small delay after each action
                await asyncio.sleep(0.1)
                
            except Exception as e:
                print(f"Error executing action {i+1}/{len(recording.actions)}: {e}")
                return False, f"Error executing action {i+1}: {str(e)}"
            
            last_timestamp = action.timestamp
        
        return True, f"Successfully executed {len(recording.actions)} actions"
        
    except Exception as e:
        return False, f"Execution failed: {str(e)}"

async def _reset_to_home_first_page(factory, device_id: str, device_type: str):
    """
    Reset device to home screen first page.
    This ensures we start recording from a consistent state.
    """
    try:
        print(f"[Reset] Resetting to home first page (device_type: {device_type})")
        
        # First, press home to go to home screen
        print(f"[Reset] Pressing home button...")
        factory.home(device_id=device_id)
        await asyncio.sleep(0.8)  # Increased wait time
        
        # For Android/HDC, try to swipe to the first page
        # We'll swipe from right to left multiple times to ensure we're on the leftmost (first) page
        if device_type in ["adb", "hdc"]:
            try:
                print(f"[Reset] Getting screen dimensions for swipe...")
                # Get screen dimensions for swipe
                screenshot = factory.get_screenshot(device_id=device_id, timeout=5)
                if screenshot:
                    screen_width = screenshot.width
                    screen_height = screenshot.height
                    print(f"[Reset] Screen size: {screen_width}x{screen_height}")
                    
                    # Swipe from right to left multiple times to ensure we're on first page
                    # This will move us to the leftmost page
                    print(f"[Reset] Swiping to first page (3 times)...")
                    for i in range(3):  # Swipe 3 times to ensure we reach the first page
                        # Swipe from 80% to 20% of screen width (right to left)
                        factory.swipe(
                            int(screen_width * 0.8),
                            int(screen_height * 0.5),
                            int(screen_width * 0.2),
                            int(screen_height * 0.5),
                            duration_ms=400,
                            device_id=device_id
                        )
                        await asyncio.sleep(0.4)
                        print(f"[Reset] Swipe {i+1}/3 completed")
                else:
                    print(f"[Reset] Warning: Failed to get screenshot")
            except Exception as e:
                print(f"[Reset] Warning: Failed to reset to home first page via swipe: {e}")
                import traceback
                traceback.print_exc()
                # Fallback: just press home again
                factory.home(device_id=device_id)
                await asyncio.sleep(0.5)
        elif device_type == "ios":
            # For iOS, swipe right to left to reach the first page
            try:
                print(f"[Reset] Getting screen dimensions for iOS swipe...")
                screenshot = factory.get_screenshot(device_id=device_id, timeout=5)
                if screenshot:
                    screen_width = screenshot.width
                    screen_height = screenshot.height
                    print(f"[Reset] iOS screen size: {screen_width}x{screen_height}")
                    # Swipe right to left (iOS home screens scroll horizontally)
                    print(f"[Reset] Swiping iOS to first page (3 times)...")
                    for i in range(3):
                        factory.swipe(
                            int(screen_width * 0.8),
                            int(screen_height * 0.5),
                            int(screen_width * 0.2),
                            int(screen_height * 0.5),
                            duration_ms=400,
                            device_id=device_id
                        )
                        await asyncio.sleep(0.4)
                        print(f"[Reset] iOS swipe {i+1}/3 completed")
            except Exception as e:
                print(f"[Reset] Warning: Failed to reset iOS home page: {e}")
                import traceback
                traceback.print_exc()
                factory.home(device_id=device_id)
                await asyncio.sleep(0.5)
        
        # Final home press to ensure we're on home screen
        print(f"[Reset] Final home press...")
        factory.home(device_id=device_id)
        await asyncio.sleep(0.8)  # Increased wait time
        print(f"[Reset] Reset to home first page completed successfully")
        
    except Exception as e:
        print(f"[Reset] Warning: Error resetting to home first page: {e}")
        import traceback
        traceback.print_exc()
        # At least ensure we're on home screen
        try:
            factory.home(device_id=device_id)
            await asyncio.sleep(0.8)
        except:
            pass

async def reset_to_initial_state(recording: Recording, device_id: str) -> Tuple[bool, str]:
    """
    Reset device to the initial state when recording started.
    
    Args:
        recording: The recording with initial_state
        device_id: Target device ID
        
    Returns:
        (success, message) tuple
    """
    try:
        print(f"[Reset] Starting reset to initial state for recording {recording.id}")
        
        # Set device type
        if recording.device_type == "hdc":
            set_device_type(DeviceType.HDC)
        elif recording.device_type == "ios":
            set_device_type(DeviceType.IOS)
        else:
            set_device_type(DeviceType.ADB)
        
        factory = get_device_factory()
        
        # Get initial state
        initial_state = recording.initial_state or {}
        current_app = initial_state.get("current_app", "")
        
        print(f"[Reset] Initial state - current_app: {current_app}")
        print(f"[Reset] Initial state - full: {initial_state}")
        
        # Check if initial state was home screen
        # "System Home" is the standard return value for home screen
        is_home_screen = (
            not current_app or 
            current_app == "Unknown" or 
            current_app == "System Home" or
            "Home" in current_app or 
            "Launcher" in current_app or
            current_app.lower() == "home"
        )
        
        print(f"[Reset] Is home screen: {is_home_screen}")
        
        # Always reset to home first page first to ensure consistent state
        print(f"[Reset] Resetting to home first page...")
        await _reset_to_home_first_page(factory, device_id, recording.device_type)
        print(f"[Reset] Reset to home first page completed")
        
        if is_home_screen:
            # If initial state was home screen, we're done
            print(f"[Reset] Initial state was home screen, reset complete")
            return True, "Reset to initial state: returned to home first page"
        else:
            # Launch the app that was active when recording started
            try:
                print(f"[Reset] Launching app: {current_app}")
                success = factory.launch_app(current_app, device_id=device_id)
                if success:
                    await asyncio.sleep(1.5)  # Wait for app to launch
                    print(f"[Reset] App launched successfully: {current_app}")
                    return True, f"Reset to initial state: returned to home first page, then launched {current_app}"
                else:
                    print(f"[Reset] Failed to launch app: {current_app}")
                    return False, f"Failed to launch app: {current_app}"
            except Exception as e:
                print(f"[Reset] Error launching app {current_app}: {e}")
                import traceback
                traceback.print_exc()
                return False, f"Error launching app {current_app}: {str(e)}"
        
    except Exception as e:
        return False, f"Reset failed: {str(e)}"

async def execute_single_action(action: RecordedAction, device_id: str, device_type: str) -> Tuple[bool, str]:
    """
    Execute a single recorded action.
    
    Args:
        action: The action to execute
        device_id: Target device ID
        device_type: Device type ("adb", "hdc", "ios")
        
    Returns:
        (success, message) tuple
    """
    try:
        # Set device type
        if device_type == "hdc":
            set_device_type(DeviceType.HDC)
        elif device_type == "ios":
            set_device_type(DeviceType.IOS)
        else:
            set_device_type(DeviceType.ADB)
        
        factory = get_device_factory()
        action_type = action.action_type
        params = action.params
        
        if action_type == "tap":
            factory.tap(params["x"], params["y"], device_id=device_id)
        elif action_type == "swipe":
            factory.swipe(
                params["x1"], params["y1"],
                params["x2"], params["y2"],
                duration_ms=params.get("duration", 500),
                device_id=device_id
            )
        elif action_type == "type":
            factory.type_text(params["text"], device_id=device_id)
        elif action_type == "back":
            factory.back(device_id=device_id)
        elif action_type == "home":
            factory.home(device_id=device_id)
        elif action_type == "recent":
            if hasattr(factory, "recent"):
                factory.recent(device_id=device_id)
            else:
                return False, "Recent apps not supported on this device type"
        elif action_type == "wait":
            await asyncio.sleep(params.get("duration", 1.0))
        else:
            return False, f"Unknown action type: {action_type}"
        
        # Small delay after action
        await asyncio.sleep(0.1)
        return True, f"Executed {action_type}"
        
    except Exception as e:
        return False, f"Error executing action: {str(e)}"

