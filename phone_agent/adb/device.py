"""Device control utilities for Android automation."""

import os
import subprocess
import time
from typing import List, Optional, Tuple

from phone_agent.config.apps import APP_PACKAGES
from phone_agent.config.timing import TIMING_CONFIG

_screen_size_cache = {}

def is_screen_on(device_id: str | None = None) -> bool:
    """
    Check if the screen is on and unlocked (not dreaming/keyguard).
    Returns True if user can interact with screen.
    """
    adb_prefix = _get_adb_prefix(device_id)
    try:
        # Check power state (Screen On/Off)
        res_power = subprocess.run(
            adb_prefix + ["shell", "dumpsys", "power"],
            capture_output=True, text=True, timeout=2
        )
        if "mWakefulness=Asleep" in res_power.stdout or "mWakefulness=Dozing" in res_power.stdout:
            return False

        # Check Keyguard/Lockscreen (Screen On but Locked)
        res_window = subprocess.run(
            adb_prefix + ["shell", "dumpsys", "window", "policy"],
            capture_output=True, text=True, timeout=2
        )
        # Common indicators of lock screen
        if "mInputRestricted=true" in res_window.stdout: # Keyguard restricted input
            return False
        if "isStatusBarKeyguard=true" in res_window.stdout: # Keyguard showing
            return False
        if "mKeyguardDrawComplete=true" in res_window.stdout and "mKeyguardOccluded=false" in res_window.stdout:
            return False
            
        return True
    except Exception:
        # If check fails, assume ON to be safe (allow retries) or OFF?
        # Assuming ON allows error recovery.
        return True

def get_screen_size(device_id: str | None = None) -> Tuple[int, int]:
    if device_id in _screen_size_cache:
        return _screen_size_cache[device_id]
    
    adb_prefix = _get_adb_prefix(device_id)
    try:
        result = subprocess.run(
            adb_prefix + ["shell", "wm", "size"], 
            capture_output=True, text=True, timeout=2
        )
        for line in result.stdout.splitlines():
            if "Physical size:" in line:
                parts = line.split(":")[1].strip().split("x")
                w, h = int(parts[0]), int(parts[1])
                _screen_size_cache[device_id] = (w, h)
                return w, h
    except Exception:
        pass
    return 1080, 2400 # Default fallback

def get_current_app(device_id: str | None = None) -> str:
    """
    Get the currently focused app name.

    Args:
        device_id: Optional ADB device ID for multi-device setups.

    Returns:
        The app name if recognized, otherwise "System Home".
    """
    adb_prefix = _get_adb_prefix(device_id)

    result = subprocess.run(
        adb_prefix + ["shell", "dumpsys", "window"], capture_output=True, text=True, encoding="utf-8"
    )
    output = result.stdout
    if not output:
        raise ValueError("No output from dumpsys window")

    # Common launcher package names (system desktop/home screen)
    LAUNCHER_PACKAGES = [
        "com.android.launcher",
        "com.android.launcher2",
        "com.android.launcher3",
        "com.huawei.android.launcher",  # Huawei
        "com.miui.home",  # Xiaomi
        "com.oppo.launcher",  # OPPO
        "com.vivo.launcher",  # vivo
        "com.samsung.android.app.launcher",  # Samsung
        "com.oneplus.launcher",  # OnePlus
        "com.meizu.flyme.launcher",  # Meizu
        "com.coloros.launcher",  # ColorOS (OPPO)
        "com.funtouch.launcher",  # Funtouch OS (vivo)
        "com.bbk.launcher2",  # vivo (older)
        "com.sec.android.app.launcher",  # Samsung (older)
        "com.sonyericsson.home",  # Sony
        "com.lge.launcher2",  # LG
        "com.htc.launcher",  # HTC
    ]

    # Parse window focus info
    for line in output.split("\n"):
        if "mCurrentFocus" in line or "mFocusedApp" in line or "mTopApp" in line:
            # First check if it's a known app
            for app_name, package in APP_PACKAGES.items():
                if package in line:
                    return app_name
            
            # Then check if it's a launcher (system desktop)
            for launcher_pkg in LAUNCHER_PACKAGES:
                if launcher_pkg in line:
                    return "System Home"
            
            # Also check for common launcher indicators in the line
            if "launcher" in line.lower() and ("activity" in line.lower() or "/" in line):
                # Extract package name from line (format: package/activity)
                parts = line.split()
                for part in parts:
                    if "/" in part and ("launcher" in part.lower() or "home" in part.lower()):
                        return "System Home"

    # Additional check: look for launcher in mTopApp or mResumedActivity
    for line in output.split("\n"):
        if "mTopApp" in line or "mResumedActivity" in line:
            for launcher_pkg in LAUNCHER_PACKAGES:
                if launcher_pkg in line:
                    return "System Home"
            if "launcher" in line.lower() and ("activity" in line.lower() or "/" in line):
                return "System Home"

    return "System Home"


def tap(
    x: int | float, y: int | float, device_id: str | None = None, delay: float | None = None
) -> None:
    """
    Tap at the specified coordinates.

    Args:
        x: X coordinate (int) or normalized (float <= 1.0).
        y: Y coordinate (int) or normalized (float <= 1.0).
        device_id: Optional ADB device ID.
        delay: Delay in seconds after tap. If None, uses configured default.
    """
    if delay is None:
        delay = TIMING_CONFIG.device.default_tap_delay

    if isinstance(x, float) and x <= 1.0:
        w, h = get_screen_size(device_id)
        x = int(x * w)
        y = int(y * h)

    adb_prefix = _get_adb_prefix(device_id)

    subprocess.run(
        adb_prefix + ["shell", "input", "tap", str(x), str(y)], capture_output=True
    )
    time.sleep(delay)


def double_tap(
    x: int, y: int, device_id: str | None = None, delay: float | None = None
) -> None:
    """
    Double tap at the specified coordinates.

    Args:
        x: X coordinate.
        y: Y coordinate.
        device_id: Optional ADB device ID.
        delay: Delay in seconds after double tap. If None, uses configured default.
    """
    if delay is None:
        delay = TIMING_CONFIG.device.default_double_tap_delay

    adb_prefix = _get_adb_prefix(device_id)

    subprocess.run(
        adb_prefix + ["shell", "input", "tap", str(x), str(y)], capture_output=True
    )
    time.sleep(TIMING_CONFIG.device.double_tap_interval)
    subprocess.run(
        adb_prefix + ["shell", "input", "tap", str(x), str(y)], capture_output=True
    )
    time.sleep(delay)


def long_press(
    x: int,
    y: int,
    duration_ms: int = 3000,
    device_id: str | None = None,
    delay: float | None = None,
) -> None:
    """
    Long press at the specified coordinates.

    Args:
        x: X coordinate.
        y: Y coordinate.
        duration_ms: Duration of press in milliseconds.
        device_id: Optional ADB device ID.
        delay: Delay in seconds after long press. If None, uses configured default.
    """
    if delay is None:
        delay = TIMING_CONFIG.device.default_long_press_delay

    adb_prefix = _get_adb_prefix(device_id)

    subprocess.run(
        adb_prefix
        + ["shell", "input", "swipe", str(x), str(y), str(x), str(y), str(duration_ms)],
        capture_output=True,
    )
    time.sleep(delay)


def swipe(
    start_x: int | float,
    start_y: int | float,
    end_x: int | float,
    end_y: int | float,
    duration_ms: int | None = None,
    device_id: str | None = None,
    delay: float | None = None,
) -> None:
    """
    Swipe from start to end coordinates.

    Args:
        start_x: Starting X coordinate.
        start_y: Starting Y coordinate.
        end_x: Ending X coordinate.
        end_y: Ending Y coordinate.
        duration_ms: Duration of swipe in milliseconds (auto-calculated if None).
        device_id: Optional ADB device ID.
        delay: Delay in seconds after swipe. If None, uses configured default.
    """
    if delay is None:
        delay = TIMING_CONFIG.device.default_swipe_delay
    
    # Scale normalized coordinates
    if isinstance(start_x, float) and start_x <= 1.0:
        w, h = get_screen_size(device_id)
        start_x = int(start_x * w)
        start_y = int(start_y * h)
        end_x = int(end_x * w)
        end_y = int(end_y * h)

    adb_prefix = _get_adb_prefix(device_id)

    if duration_ms is None:
        # Calculate duration based on distance
        dist_sq = (start_x - end_x) ** 2 + (start_y - end_y) ** 2
        duration_ms = int(dist_sq / 1000)
        duration_ms = max(1000, min(duration_ms, 2000))  # Clamp between 1000-2000ms

    subprocess.run(
        adb_prefix
        + [
            "shell",
            "input",
            "swipe",
            str(start_x),
            str(start_y),
            str(end_x),
            str(end_y),
            str(duration_ms),
        ],
        capture_output=True,
    )
    time.sleep(delay)


def back(device_id: str | None = None, delay: float | None = None) -> None:
    """
    Press the back button.

    Args:
        device_id: Optional ADB device ID.
        delay: Delay in seconds after pressing back. If None, uses configured default.
    """
    if delay is None:
        delay = TIMING_CONFIG.device.default_back_delay

    adb_prefix = _get_adb_prefix(device_id)

    subprocess.run(
        adb_prefix + ["shell", "input", "keyevent", "4"], capture_output=True
    )
    time.sleep(delay)


def home(device_id: str | None = None, delay: float | None = None) -> None:
    """
    Press the home button.

    Args:
        device_id: Optional ADB device ID.
        delay: Delay in seconds after pressing home. If None, uses configured default.
    """
    if delay is None:
        delay = TIMING_CONFIG.device.default_home_delay

    adb_prefix = _get_adb_prefix(device_id)

    subprocess.run(
        adb_prefix + ["shell", "input", "keyevent", "KEYCODE_HOME"], capture_output=True
    )
    time.sleep(delay)


def recent(device_id: str | None = None, delay: float | None = None) -> None:
    """
    Press the recent apps button.

    Args:
        device_id: Optional ADB device ID.
        delay: Delay in seconds.
    """
    if delay is None:
        delay = TIMING_CONFIG.device.default_home_delay

    adb_prefix = _get_adb_prefix(device_id)

    subprocess.run(
        adb_prefix + ["shell", "input", "keyevent", "KEYCODE_APP_SWITCH"], capture_output=True
    )
    time.sleep(delay)


def get_installed_packages(device_id: str | None = None, include_system: bool = True) -> List[str]:
    """Get list of installed packages."""
    adb_prefix = _get_adb_prefix(device_id)
    cmd = adb_prefix + ["shell", "pm", "list", "packages"]
    if not include_system:
        cmd.append("-3")
        
    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=5
        )
        packages = []
        for line in result.stdout.splitlines():
            if line.startswith("package:"):
                packages.append(line.split(":", 1)[1].strip())
        return packages
    except Exception:
        return []


def launch_app(
    app_name: str, device_id: str | None = None, delay: float | None = None
) -> bool:
    """
    Launch an app by name.

    Args:
        app_name: The app name (must be in APP_PACKAGES).
        device_id: Optional ADB device ID.
        delay: Delay in seconds after launching. If None, uses configured default.

    Returns:
        True if app was launched, False if app not found.
    """
    if delay is None:
        delay = TIMING_CONFIG.device.default_launch_delay

    package = None
    if app_name in APP_PACKAGES:
        package = APP_PACKAGES[app_name]
    else:
        # Req 2: Dynamic fallback
        # Try to find in installed packages
        print(f"[Device] App '{app_name}' not in config, searching installed packages...")
        installed = get_installed_packages(device_id)
        # Simple heuristic: fuzzy match
        normalized_name = app_name.lower()
        
        # Exact substring match
        matches = [pkg for pkg in installed if normalized_name in pkg.lower()]
        
        if matches:
            # Pick shortest one (usually the main app)
            matches.sort(key=len)
            package = matches[0]
            print(f"[Device] Dynamic app match: {app_name} -> {package}")
        else:
            print(f"[Device] App '{app_name}' not found on device.")
            return False

    adb_prefix = _get_adb_prefix(device_id)

    subprocess.run(
        adb_prefix
        + [
            "shell",
            "monkey",
            "-p",
            package,
            "-c",
            "android.intent.category.LAUNCHER",
            "1",
        ],
        capture_output=True,
    )
    time.sleep(delay)
    return True


def _get_adb_prefix(device_id: str | None) -> list:
    """Get ADB command prefix with optional device specifier."""
    if device_id:
        return ["adb", "-s", device_id]
    return ["adb"]
