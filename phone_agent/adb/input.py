"""Input utilities for Android device text input."""

import base64
import subprocess
from typing import Optional


def type_text(text: str, device_id: str | None = None) -> None:
    """
    Type text into the currently focused input field using ADB Keyboard.

    Args:
        text: The text to type.
        device_id: Optional ADB device ID for multi-device setups.

    Note:
        Requires ADB Keyboard to be installed on the device.
        See: https://github.com/nicnocquee/AdbKeyboard
    """
    # Skip if text is empty - empty text causes command error
    if not text:
        print(f"[ADB Type Debug] Skipping empty text input (would cause command error)", flush=True)
        return
    
    adb_prefix = _get_adb_prefix(device_id)
    encoded_text = base64.b64encode(text.encode("utf-8")).decode("utf-8")
    
    print(f"[ADB Type Debug] Typing text: '{text}' (length: {len(text)}, encoded length: {len(encoded_text)})", flush=True)
    
    # Check current IME before typing
    ime_check = subprocess.run(
        adb_prefix + ["shell", "settings", "get", "secure", "default_input_method"],
        capture_output=True,
        text=True,
    )
    current_ime = (ime_check.stdout + ime_check.stderr).strip()
    print(f"[ADB Type Debug] Current IME before typing: '{current_ime}'", flush=True)
    if "com.android.adbkeyboard/.AdbIME" not in current_ime:
        print(f"[ADB Type Debug] ✗ WARNING: ADB Keyboard is not active! Input may fail.", flush=True)

    result = subprocess.run(
        adb_prefix
        + [
            "shell",
            "am",
            "broadcast",
            "-a",
            "ADB_INPUT_B64",
            "--es",
            "msg",
            encoded_text,
        ],
        capture_output=True,
        text=True,
    )
    
    print(f"[ADB Type Debug] Type command result (returncode: {result.returncode})", flush=True)
    if result.stdout:
        print(f"[ADB Type Debug] Type command stdout: {result.stdout.strip()}", flush=True)
    if result.stderr:
        print(f"[ADB Type Debug] Type command stderr: {result.stderr.strip()}", flush=True)
    if result.returncode != 0:
        print(f"[ADB Type Debug] ✗ Type command failed with returncode {result.returncode}", flush=True)


def clear_text(device_id: str | None = None) -> None:
    """
    Clear text in the currently focused input field.

    Args:
        device_id: Optional ADB device ID for multi-device setups.
    """
    adb_prefix = _get_adb_prefix(device_id)
    
    print(f"[ADB Clear Debug] Clearing text...", flush=True)

    result = subprocess.run(
        adb_prefix + ["shell", "am", "broadcast", "-a", "ADB_CLEAR_TEXT"],
        capture_output=True,
        text=True,
    )
    
    print(f"[ADB Clear Debug] Clear command result (returncode: {result.returncode})", flush=True)
    if result.stdout:
        print(f"[ADB Clear Debug] Clear command stdout: {result.stdout.strip()}", flush=True)
    if result.stderr:
        print(f"[ADB Clear Debug] Clear command stderr: {result.stderr.strip()}", flush=True)
    if result.returncode != 0:
        print(f"[ADB Clear Debug] ✗ Clear command failed with returncode {result.returncode}", flush=True)


def detect_and_set_adb_keyboard(device_id: str | None = None) -> str:
    """
    Detect current keyboard and switch to ADB Keyboard if needed.

    Args:
        device_id: Optional ADB device ID for multi-device setups.

    Returns:
        The original keyboard IME identifier for later restoration.
    """
    adb_prefix = _get_adb_prefix(device_id)

    # Get current IME
    print(f"[ADB Keyboard Debug] Getting current IME...", flush=True)
    result = subprocess.run(
        adb_prefix + ["shell", "settings", "get", "secure", "default_input_method"],
        capture_output=True,
        text=True,
    )
    current_ime = (result.stdout + result.stderr).strip()
    print(f"[ADB Keyboard Debug] Current IME: '{current_ime}' (returncode: {result.returncode})", flush=True)
    if result.stderr:
        print(f"[ADB Keyboard Debug] IME command stderr: {result.stderr}", flush=True)

    # Check if ADB Keyboard is installed
    print(f"[ADB Keyboard Debug] Checking if ADB Keyboard is installed...", flush=True)
    check_result = subprocess.run(
        adb_prefix + ["shell", "pm", "list", "packages", "com.android.adbkeyboard"],
        capture_output=True,
        text=True,
    )
    if "com.android.adbkeyboard" in check_result.stdout:
        print(f"[ADB Keyboard Debug] ✓ ADB Keyboard is installed", flush=True)
    else:
        print(f"[ADB Keyboard Debug] ✗ ADB Keyboard is NOT installed! This will cause input to fail.", flush=True)
        print(f"[ADB Keyboard Debug] Please install ADB Keyboard: https://github.com/nicnocquee/AdbKeyboard", flush=True)

    # List available IMEs
    print(f"[ADB Keyboard Debug] Listing available IMEs...", flush=True)
    ime_list_result = subprocess.run(
        adb_prefix + ["shell", "ime", "list", "-s"],
        capture_output=True,
        text=True,
    )
    print(f"[ADB Keyboard Debug] Available IMEs: {ime_list_result.stdout.strip()}", flush=True)

    # Switch to ADB Keyboard if not already set
    if "com.android.adbkeyboard/.AdbIME" not in current_ime:
        print(f"[ADB Keyboard Debug] Switching to ADB Keyboard...", flush=True)
        switch_result = subprocess.run(
            adb_prefix + ["shell", "ime", "set", "com.android.adbkeyboard/.AdbIME"],
            capture_output=True,
            text=True,
        )
        print(f"[ADB Keyboard Debug] Switch result (returncode: {switch_result.returncode}): {switch_result.stdout.strip()}", flush=True)
        if switch_result.stderr:
            print(f"[ADB Keyboard Debug] Switch stderr: {switch_result.stderr}", flush=True)
        
        # Verify the switch
        verify_result = subprocess.run(
            adb_prefix + ["shell", "settings", "get", "secure", "default_input_method"],
            capture_output=True,
            text=True,
        )
        new_ime = (verify_result.stdout + verify_result.stderr).strip()
        print(f"[ADB Keyboard Debug] Verified IME after switch: '{new_ime}'", flush=True)
        if "com.android.adbkeyboard/.AdbIME" not in new_ime:
            print(f"[ADB Keyboard Debug] ✗ WARNING: Failed to switch to ADB Keyboard!", flush=True)
    else:
        print(f"[ADB Keyboard Debug] ADB Keyboard is already active", flush=True)

    # Warm up the keyboard (skip if text is empty to avoid command error)
    print(f"[ADB Keyboard Debug] Warming up keyboard...", flush=True)
    # Note: type_text("") would fail because --es requires a value, so we skip warm up for empty text
    # The keyboard should be ready after switching IME
    print(f"[ADB Keyboard Debug] Skipping warm up (empty text would cause command error)", flush=True)

    return current_ime


def restore_keyboard(ime: str, device_id: str | None = None) -> None:
    """
    Restore the original keyboard IME.

    Args:
        ime: The IME identifier to restore.
        device_id: Optional ADB device ID for multi-device setups.
    """
    adb_prefix = _get_adb_prefix(device_id)

    subprocess.run(
        adb_prefix + ["shell", "ime", "set", ime], capture_output=True, text=True
    )


def _get_adb_prefix(device_id: str | None) -> list:
    """Get ADB command prefix with optional device specifier."""
    if device_id:
        return ["adb", "-s", device_id]
    return ["adb"]
