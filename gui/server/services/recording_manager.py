"""Recording manager for capturing and replaying device actions."""

import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import os
import threading

@dataclass
class RecordedAction:
    """A single recorded action."""
    action_type: str  # "tap", "swipe", "type", "back", "home", "recent", "wait"
    timestamp: float  # Time since recording started (seconds)
    params: Dict[str, Any]  # Action-specific parameters
    
@dataclass
class Recording:
    """A complete recording with metadata."""
    id: str
    name: str
    keywords: List[str]
    device_id: str
    device_type: str  # "adb", "hdc", "ios"
    actions: List[RecordedAction]
    created_at: str
    updated_at: str
    description: Optional[str] = None
    initial_state: Optional[Dict[str, Any]] = None  # Device state when recording started

class RecordingManager:
    """Manages action recordings for devices."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self._recordings: Dict[str, Recording] = {}
        self._active_recordings: Dict[str, Dict[str, Any]] = {}  # device_id -> recording data
        self._storage_path = os.path.join(os.path.dirname(__file__), "../../../data/recordings")
        os.makedirs(self._storage_path, exist_ok=True)
        
        self._load_recordings()
    
    def _load_recordings(self):
        """Load all recordings from disk."""
        try:
            index_file = os.path.join(self._storage_path, "index.json")
            if os.path.exists(index_file):
                with open(index_file, 'r', encoding='utf-8') as f:
                    index = json.load(f)
                    
                for recording_id in index.get("recordings", []):
                    recording_file = os.path.join(self._storage_path, f"{recording_id}.json")
                    if os.path.exists(recording_file):
                        try:
                            with open(recording_file, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                recording = self._dict_to_recording(data)
                                self._recordings[recording_id] = recording
                        except Exception as e:
                            print(f"Error loading recording {recording_id}: {e}")
        except Exception as e:
            print(f"Error loading recordings index: {e}")
    
    def _save_recordings_index(self):
        """Save recordings index to disk."""
        try:
            index_file = os.path.join(self._storage_path, "index.json")
            index = {
                "recordings": list(self._recordings.keys()),
                "updated_at": datetime.now().isoformat()
            }
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving recordings index: {e}")
    
    def _save_recording(self, recording: Recording):
        """Save a single recording to disk."""
        try:
            recording_file = os.path.join(self._storage_path, f"{recording.id}.json")
            data = self._recording_to_dict(recording)
            with open(recording_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._save_recordings_index()
        except Exception as e:
            print(f"Error saving recording {recording.id}: {e}")
    
    def _recording_to_dict(self, recording: Recording) -> Dict[str, Any]:
        """Convert Recording to dictionary."""
        return {
            "id": recording.id,
            "name": recording.name,
            "keywords": recording.keywords,
            "device_id": recording.device_id,
            "device_type": recording.device_type,
            "actions": [asdict(action) for action in recording.actions],
            "created_at": recording.created_at,
            "updated_at": recording.updated_at,
            "description": recording.description,
            "initial_state": recording.initial_state
        }
    
    def _dict_to_recording(self, data: Dict[str, Any]) -> Recording:
        """Convert dictionary to Recording."""
        actions = [RecordedAction(**action) for action in data.get("actions", [])]
        return Recording(
            id=data["id"],
            name=data["name"],
            keywords=data.get("keywords", []),
            device_id=data["device_id"],
            device_type=data.get("device_type", "adb"),
            actions=actions,
            created_at=data["created_at"],
            updated_at=data.get("updated_at", data["created_at"]),
            description=data.get("description"),
            initial_state=data.get("initial_state")
        )
    
    def start_recording(self, device_id: str, device_type: str = "adb", initial_state: Optional[Dict[str, Any]] = None) -> str:
        """Start recording actions for a device.
        
        Args:
            device_id: Device ID
            device_type: Device type ("adb", "hdc", "ios")
            initial_state: Optional initial device state (current_app, screen_info, etc.)
        """
        recording_id = f"rec_{int(time.time() * 1000)}"
        self._active_recordings[device_id] = {
            "id": recording_id,
            "device_id": device_id,
            "device_type": device_type,
            "start_time": time.time(),
            "actions": [],
            "initial_state": initial_state or {}
        }
        return recording_id
    
    def stop_recording(self, device_id: str) -> Optional[str]:
        """Stop recording and return recording ID.
        
        Note: Recording data is kept in _active_recordings until saved or discarded.
        This allows preview and debug before saving.
        """
        if device_id not in self._active_recordings:
            return None
        
        # Don't remove from _active_recordings yet - keep it for preview/debug
        # It will be removed when saved via save_recording()
        recording_data = self._active_recordings[device_id]
        return recording_data["id"]
    
    def is_recording(self, device_id: str) -> bool:
        """Check if recording is active for a device."""
        return device_id in self._active_recordings
    
    def record_action(self, device_id: str, action_type: str, params: Dict[str, Any]):
        """Record an action for the active recording."""
        if device_id not in self._active_recordings:
            return
        
        recording_data = self._active_recordings[device_id]
        elapsed = time.time() - recording_data["start_time"]
        
        action = RecordedAction(
            action_type=action_type,
            timestamp=elapsed,
            params=params
        )
        recording_data["actions"].append(action)
    
    def save_recording(self, recording_id: str, name: str, keywords: List[str], 
                      description: Optional[str] = None) -> Optional[Recording]:
        """Save a recording with metadata."""
        # Find the recording in active recordings
        recording_data = None
        for device_id, data in self._active_recordings.items():
            if data["id"] == recording_id:
                recording_data = data
                break
        
        if not recording_data:
            return None
        
        # Create Recording object
        now = datetime.now().isoformat()
        actions = [RecordedAction(**asdict(action)) for action in recording_data["actions"]]
        
        recording = Recording(
            id=recording_id,
            name=name,
            keywords=keywords,
            device_id=recording_data["device_id"],
            device_type=recording_data["device_type"],
            actions=actions,
            created_at=now,
            updated_at=now,
            description=description,
            initial_state=recording_data.get("initial_state")
        )
        
        # Save to memory and disk
        self._recordings[recording_id] = recording
        self._save_recording(recording)
        
        # Remove from active recordings
        if recording_data["device_id"] in self._active_recordings:
            del self._active_recordings[recording_data["device_id"]]
        
        return recording
    
    def get_recording(self, recording_id: str) -> Optional[Recording]:
        """Get a recording by ID."""
        return self._recordings.get(recording_id)
    
    def list_recordings(self, device_id: Optional[str] = None, 
                       keyword: Optional[str] = None) -> List[Recording]:
        """List all recordings, optionally filtered by device or keyword."""
        recordings = list(self._recordings.values())
        
        if device_id:
            recordings = [r for r in recordings if r.device_id == device_id]
        
        if keyword:
            keyword_lower = keyword.lower()
            filtered = []
            for r in recordings:
                if (keyword_lower in r.name.lower() or 
                    any(keyword_lower in k.lower() for k in r.keywords)):
                    filtered.append(r)
            recordings = filtered
        
        # Sort by updated_at descending
        recordings.sort(key=lambda x: x.updated_at, reverse=True)
        return recordings
    
    def delete_recording(self, recording_id: str) -> bool:
        """Delete a recording."""
        if recording_id not in self._recordings:
            return False
        
        # Remove from memory
        del self._recordings[recording_id]
        
        # Remove from disk
        try:
            recording_file = os.path.join(self._storage_path, f"{recording_id}.json")
            if os.path.exists(recording_file):
                os.remove(recording_file)
            self._save_recordings_index()
        except Exception as e:
            print(f"Error deleting recording file: {e}")
        
        return True
    
    def get_active_recording_data(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get active recording data for a device."""
        return self._active_recordings.get(device_id)

# Global instance
recording_manager = RecordingManager()

