import time
import uuid
import socket
import subprocess
from typing import Optional, List, Dict
from pydantic import BaseModel
import shutil
from phone_agent.adb import list_devices as adb_list_devices, ADBConnection
from phone_agent.hdc import list_devices as hdc_list_devices, HDCConnection

class DeviceInfo(BaseModel):
    id: str
    type: str  # 'adb' or 'hdc'
    status: str
    connection_type: str # 'usb' or 'wifi'
    brand: Optional[str] = None  # Device brand (e.g., 'Huawei', 'Xiaomi')

class DeviceManager:
    _instance = None
    
    def __init__(self):
        self.active_device_id: Optional[str] = None
        self.active_device_type: str = "adb"  # default
        self.adb_connection = ADBConnection()
        self.hdc_connection = HDCConnection()
        self.adb_path = shutil.which("adb")
        self.hdc_path = shutil.which("hdc")
        self.webrtc_devices = []  # List of manually added WebRTC devices
        self.pending_sessions = {} # token -> session_info
        self.device_permissions: Dict[str, Dict[str, bool]] = {} # device_id -> permissions

    def get_device_permissions(self, device_id: str) -> Dict[str, bool]:
        # Default permissions: All sensitive actions require approval (False)
        return self.device_permissions.get(device_id, {
            "install_app": False,
            "payment": False,
            "wechat_reply": False,
            "send_sms": False,
            "make_call": False
        })

    def set_device_permissions(self, device_id: str, permissions: Dict[str, bool]):
        self.device_permissions[device_id] = permissions

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_device_brand(self, device_id: str, device_type: str) -> Optional[str]:
        """Get device brand using ADB/HDC commands."""
        try:
            if device_type == "adb" and self.adb_path:
                # Try ro.product.brand first, then ro.product.manufacturer
                for prop in ["ro.product.brand", "ro.product.manufacturer"]:
                    result = subprocess.run(
                        [self.adb_path, "-s", device_id, "shell", "getprop", prop],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        brand = result.stdout.strip()
                        # Normalize brand names
                        return self._normalize_brand(brand)
            elif device_type == "hdc" and self.hdc_path:
                # Try to get brand for HarmonyOS devices
                for prop in ["hw_sc.build.platform.name", "ro.product.brand"]:
                    result = subprocess.run(
                        [self.hdc_path, "-t", device_id, "shell", "param get", prop],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        brand = result.stdout.strip()
                        return self._normalize_brand(brand)
        except Exception as e:
            print(f"Error getting device brand for {device_id}: {e}")
        return None
    
    def _normalize_brand(self, brand: str) -> str:
        """Normalize brand names to common formats."""
        brand_lower = brand.lower().strip()
        # Map common variations to standard names
        brand_map = {
            "huawei": "华为",
            "honor": "荣耀",
            "xiaomi": "小米",
            "redmi": "红米",
            "oppo": "OPPO",
            "oneplus": "一加",
            "vivo": "vivo",
            "iqoo": "iQOO",
            "samsung": "三星",
            "meizu": "魅族",
            "realme": "realme",
            "motorola": "摩托罗拉",
            "lenovo": "联想",
            "zte": "中兴",
            "coolpad": "酷派",
            "gionee": "金立",
            "nubia": "努比亚",
            "smartisan": "锤子",
            "360": "360",
            "leeco": "乐视",
        }
        
        # Check exact match first
        if brand_lower in brand_map:
            return brand_map[brand_lower]
        
        # Check partial match
        for key, value in brand_map.items():
            if key in brand_lower or brand_lower in key:
                return value
        
        # Return capitalized original if no match
        return brand.strip().title()

    def _get_device_brand(self, device_id: str, device_type: str) -> Optional[str]:
        """Get device brand using ADB/HDC commands."""
        try:
            if device_type == "adb" and self.adb_path:
                # Try ro.product.brand first, then ro.product.manufacturer
                for prop in ["ro.product.brand", "ro.product.manufacturer"]:
                    result = subprocess.run(
                        [self.adb_path, "-s", device_id, "shell", "getprop", prop],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        brand = result.stdout.strip()
                        # Normalize brand names
                        return self._normalize_brand(brand)
            elif device_type == "hdc" and self.hdc_path:
                # Try to get brand for HarmonyOS devices
                for prop in ["hw_sc.build.platform.name", "ro.product.brand"]:
                    result = subprocess.run(
                        [self.hdc_path, "-t", device_id, "shell", "param get", prop],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        brand = result.stdout.strip()
                        return self._normalize_brand(brand)
        except Exception as e:
            print(f"Error getting device brand for {device_id}: {e}")
        return None
    
    def _normalize_brand(self, brand: str) -> str:
        """Normalize brand names to common formats."""
        brand_lower = brand.lower().strip()
        # Map common variations to standard names
        brand_map = {
            "huawei": "华为",
            "honor": "荣耀",
            "xiaomi": "小米",
            "redmi": "红米",
            "oppo": "OPPO",
            "oneplus": "一加",
            "vivo": "vivo",
            "iqoo": "iQOO",
            "samsung": "三星",
            "meizu": "魅族",
            "realme": "realme",
            "motorola": "摩托罗拉",
            "lenovo": "联想",
            "zte": "中兴",
            "coolpad": "酷派",
            "gionee": "金立",
            "nubia": "努比亚",
            "smartisan": "锤子",
            "360": "360",
            "leeco": "乐视",
        }
        
        # Check exact match first
        if brand_lower in brand_map:
            return brand_map[brand_lower]
        
        # Check partial match
        for key, value in brand_map.items():
            if key in brand_lower or brand_lower in key:
                return value
        
        # Return capitalized original if no match
        return brand.strip().title()

    def list_all_devices(self) -> List[DeviceInfo]:
        devices = []
        
        # Check if tools exist
        if not self.adb_path:
            # Try to re-detect in case it was added to PATH later
            self.adb_path = shutil.which("adb")
            if not self.adb_path:
                print("Warning: 'adb' executable not found in PATH.")
        
        if not self.hdc_path:
            self.hdc_path = shutil.which("hdc")

        # List ADB Devices
        if self.adb_path:
            try:
                adb_devices = adb_list_devices()
                for d in adb_devices:
                    brand = self._get_device_brand(d.device_id, "adb")
                    print(f"Device {d.device_id} brand: {brand}")  # Debug log
                    devices.append(DeviceInfo(
                        id=d.device_id,
                        type="adb",
                        status="device", # Simplified for now
                        connection_type=d.connection_type.value,
                        brand=brand
                    ))
            except Exception as e:
                print(f"Error listing ADB devices: {e}")

        # List HDC Devices
        if self.hdc_path:
            try:
                hdc_devices = hdc_list_devices()
                for d in hdc_devices:
                    brand = self._get_device_brand(d.device_id, "hdc")
                    devices.append(DeviceInfo(
                        id=d.device_id,
                        type="hdc",
                        status="device",
                        connection_type=d.connection_type.value,
                        brand=brand or "华为"  # HarmonyOS devices are typically Huawei
                    ))
            except Exception as e:
                print(f"Error listing HDC devices: {e}")
                
        # List WebRTC Devices
        for wd in self.webrtc_devices:
            devices.append(DeviceInfo(
                id=wd['id'],
                type="webrtc",
                status=wd.get('status', 'connected'),
                connection_type="remote",
                brand=wd.get('brand')  # WebRTC devices might have brand info
            ))
            
        return devices

    def init_webrtc_session(self):
        """Generate a new session for a device to connect to."""
        token = str(uuid.uuid4())
        
        # Detect local IP
        local_ip = "127.0.0.1"
        try:
            # Method 1: Try to get all interfaces and pick a 192.168.* one
            hostname = socket.gethostname()
            # This often returns localhost, so we look at interfaces
            # But python's socket.gethostbyname_ex might work
            _, _, ip_list = socket.gethostbyname_ex(hostname)
            
            # Filter for 192.168.* or 10.* or 172.*, but prioritize 192.168
            preferred_ips = [ip for ip in ip_list if ip.startswith("192.168.")]
            
            if preferred_ips:
                local_ip = preferred_ips[0]
            else:
                # Fallback to the connect method if no obvious LAN IP found
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                detected_ip = s.getsockname()[0]
                s.close()
                # Avoid 198.18.* if possible unless it's the only one
                if not detected_ip.startswith("198.18."):
                    local_ip = detected_ip
                elif ip_list:
                     # If connect gave us 198.18, try to pick another non-localhost one
                     others = [ip for ip in ip_list if not ip.startswith("127.") and not ip.startswith("198.18.")]
                     if others:
                         local_ip = others[0]
                     else:
                         local_ip = detected_ip # Fallback to it if nothing else
                         
        except Exception:
            # Hardcoded fallback if detection fails completely
            local_ip = "192.168.31.232" 
            
        # Using 8000 as per new config.
        # Update: Generate HTTP URL for the mobile client page
        ws_url = f"https://{local_ip}:8000/api/devices/client/{token}"
        
        self.pending_sessions[token] = {
            "status": "pending",
            "created_at": time.time()
        }
        return token, ws_url

    def register_webrtc_connection(self, token: str, device_id: str, websocket):
        """Register a successful WebSocket connection from a device."""
        if token in self.pending_sessions:
            self.webrtc_devices.append({
                "id": device_id,
                "type": "webrtc",
                "token": token,
                "socket": websocket,
                "status": "connected" # Track status
            })
            del self.pending_sessions[token]
            return True
        return False

    def handle_webrtc_disconnect(self, token: str):
        """Mark device as offline on disconnect."""
        for d in self.webrtc_devices:
            if d.get("token") == token:
                d["status"] = "offline"
                d["socket"] = None
                break

    def update_webrtc_device(self, token: str, data: dict):
        """Update device info (e.g. latest screenshot)."""
        for d in self.webrtc_devices:
            if d.get("token") == token:
                d.update(data)
                break

    def add_webrtc_device(self, url: str) -> bool:
        # Simple registration for now. 
        # In a real scenario, we would ping the signaling server.
        device_id = url.replace("ws://", "").replace("wss://", "").replace("/", "_")
        
        # Check if already exists
        for d in self.webrtc_devices:
            if d['id'] == device_id:
                return True
                
        self.webrtc_devices.append({
            "id": device_id,
            "url": url
        })
        return True

    def remove_device(self, device_id: str) -> bool:
        """Remove a device (only applicable for WebRTC/Offline devices)."""
        original_count = len(self.webrtc_devices)
        self.webrtc_devices = [d for d in self.webrtc_devices if d['id'] != device_id]
        
        # If we removed the active device, clear selection
        if self.active_device_id == device_id:
            self.active_device_id = None
            
        return len(self.webrtc_devices) < original_count

    def set_active_device(self, device_id: str, device_type: str):
        self.active_device_id = device_id
        self.active_device_type = device_type
        # Set environment variables for the agent process if needed
        # os.environ["PHONE_AGENT_DEVICE_ID"] = device_id
        
    def connect_remote(self, address: str, device_type: str = "adb") -> bool:
        if device_type == "adb":
            success, _ = self.adb_connection.connect(address)
            return success
        elif device_type == "hdc":
            success, _ = self.hdc_connection.connect(address)
            return success
        return False
        
    def enable_tcpip(self, device_id: Optional[str] = None) -> bool:
        success, _ = self.adb_connection.enable_tcpip(device_id=device_id)
        return success

    def get_device_ip(self, device_id: Optional[str] = None) -> Optional[str]:
        return self.adb_connection.get_device_ip(device_id=device_id)

device_manager = DeviceManager.get_instance()
