"""Configuration manager for app matching rules and LLM prompts."""

from typing import Dict, Any, Optional
import json
import os

class ConfigManager:
    _instance = None
    
    # Default system app mappings
    DEFAULT_SYSTEM_APP_MAPPINGS = {
        "应用市场": [
            "com.huawei.appmarket",
            "com.xiaomi.market",
            "com.oppo.market",
            "com.vivo.appstore",
            "com.samsung.android.apps.samsungapps",
            "com.tencent.android.qqdownloader",
            "com.qihoo.appstore",
            "com.baidu.appsearch",
            "com.wandoujia.phoenix2",
            "com.yingyonghui.market",
        ],
        "应用商店": [
            "com.huawei.appmarket",
            "com.xiaomi.market",
            "com.oppo.market",
            "com.vivo.appstore",
            "com.samsung.android.apps.samsungapps",
        ],
        "app store": [
            "com.huawei.appmarket",
            "com.xiaomi.market",
            "com.oppo.market",
            "com.vivo.appstore",
            "com.samsung.android.apps.samsungapps",
        ],
        "market": [
            "com.huawei.appmarket",
            "com.xiaomi.market",
            "com.oppo.market",
            "com.vivo.appstore",
        ],
        "短信": [
            "com.android.mms",
            "com.android.messaging",
            "com.huawei.mms",
            "com.miui.mms",
            "com.coloros.mms",
            "com.funtouch.mms",
            "com.samsung.android.messaging",
        ],
        "信息": [
            "com.android.mms",
            "com.android.messaging",
            "com.huawei.mms",
            "com.miui.mms",
        ],
        "消息": [
            "com.android.mms",
            "com.android.messaging",
            "com.huawei.mms",
            "com.miui.mms",
        ],
        "sms": [
            "com.android.mms",
            "com.android.messaging",
            "com.huawei.mms",
            "com.miui.mms",
        ],
        "电话": [
            "com.android.dialer",
            "com.android.contacts",
            "com.huawei.contacts",
            "com.miui.dialer",
            "com.coloros.dialer",
            "com.funtouch.dialer",
            "com.samsung.android.dialer",
        ],
        "拨号": [
            "com.android.dialer",
            "com.huawei.contacts",
            "com.miui.dialer",
            "com.coloros.dialer",
        ],
        "拨号器": [
            "com.android.dialer",
            "com.huawei.contacts",
            "com.miui.dialer",
        ],
        "phone": [
            "com.android.dialer",
            "com.android.contacts",
            "com.huawei.contacts",
            "com.miui.dialer",
        ],
        "dialer": [
            "com.android.dialer",
            "com.huawei.contacts",
            "com.miui.dialer",
        ],
        "联系人": [
            "com.android.contacts",
            "com.huawei.contacts",
            "com.miui.contacts",
            "com.coloros.contacts",
            "com.funtouch.contacts",
            "com.samsung.android.contacts",
        ],
        "通讯录": [
            "com.android.contacts",
            "com.huawei.contacts",
            "com.miui.contacts",
            "com.coloros.contacts",
        ],
        "contacts": [
            "com.android.contacts",
            "com.huawei.contacts",
            "com.miui.contacts",
        ],
    }
    
    # Default LLM prompt template
    DEFAULT_LLM_PROMPT_TEMPLATE = """请根据用户输入的应用名称或描述，在已安装应用列表中查找匹配的应用。

用户输入：{user_input}

已安装应用列表：
{apps_text}

系统应用提示（如果用户输入匹配以下关键词，优先查找这些包名）：
{system_hints_text}

请分析用户输入是否匹配已安装应用列表中的某个应用。匹配规则：
1. 如果用户输入是应用名称（如"微信"、"抖音"），查找列表中名称相同或相似的应用
2. 如果用户输入是包名（如"com.tencent.mm"），查找列表中包名相同的应用
3. 如果用户输入是应用描述（如"聊天软件"、"视频应用"），根据应用名称推断匹配
4. 对于系统应用（如"应用市场"、"短信"、"电话"、"联系人"），优先匹配系统应用提示中的包名
5. 注意：不同品牌手机的系统应用包名可能不同（如华为、小米、OPPO、vivo等），需要根据实际已安装列表匹配

如果匹配成功，请返回：
- installed: true
- package_id: 匹配的应用包名
- app_name: 匹配的应用名称
- reason: 匹配原因说明

如果未匹配到任何应用，请返回：
- installed: false
- package_id: null
- app_name: null
- reason: 未找到匹配的应用

请严格按照以下JSON格式返回，不要添加任何其他内容：
{{
    "installed": true,
    "package_id": "com.example.app",
    "app_name": "应用名称",
    "reason": "匹配原因说明"
}}"""
    
    def __init__(self):
        self.config_file = os.path.join(os.path.dirname(__file__), "..", "..", "config", "app_matching_config.json")
        self._config: Dict[str, Any] = {}
        self._load_config()
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def _load_config(self):
        """Load configuration from file or use defaults."""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
            else:
                # Initialize with defaults
                self._config = {
                    "system_app_mappings": self.DEFAULT_SYSTEM_APP_MAPPINGS,
                    "llm_prompt_template": self.DEFAULT_LLM_PROMPT_TEMPLATE
                }
                self._save_config()
        except Exception as e:
            print(f"Error loading config: {e}")
            # Use defaults on error
            self._config = {
                "system_app_mappings": self.DEFAULT_SYSTEM_APP_MAPPINGS,
                "llm_prompt_template": self.DEFAULT_LLM_PROMPT_TEMPLATE
            }
    
    def _save_config(self):
        """Save configuration to file."""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get_system_app_mappings(self) -> Dict[str, list]:
        """Get system app mappings.
        
        Returns mappings in format: {keyword: [package1, package2, ...]}
        Supports both old format (list of strings) and new format (list of dicts with 'package' and 'platform').
        """
        mappings = self._config.get("system_app_mappings", self.DEFAULT_SYSTEM_APP_MAPPINGS)
        
        # Convert new format to old format for backward compatibility
        converted = {}
        for keyword, packages in mappings.items():
            if isinstance(packages, list) and len(packages) > 0:
                if isinstance(packages[0], dict):
                    # New format: list of dicts
                    converted[keyword] = [pkg.get("package", "") for pkg in packages if pkg.get("package")]
                else:
                    # Old format: list of strings
                    converted[keyword] = packages
            else:
                converted[keyword] = packages
        
        return converted
    
    def get_llm_prompt_template(self) -> str:
        """Get LLM prompt template."""
        return self._config.get("llm_prompt_template", self.DEFAULT_LLM_PROMPT_TEMPLATE)
    
    def update_system_app_mappings(self, mappings: Dict[str, list]):
        """Update system app mappings."""
        self._config["system_app_mappings"] = mappings
        self._save_config()
    
    def update_llm_prompt_template(self, template: str):
        """Update LLM prompt template."""
        self._config["llm_prompt_template"] = template
        self._save_config()
    
    def update_config(self, system_app_mappings: Optional[Dict[str, list]] = None, 
                     llm_prompt_template: Optional[str] = None):
        """Update configuration."""
        if system_app_mappings is not None:
            self._config["system_app_mappings"] = system_app_mappings
        if llm_prompt_template is not None:
            self._config["llm_prompt_template"] = llm_prompt_template
        self._save_config()
    
    def get_all_config(self) -> Dict[str, Any]:
        """Get all configuration."""
        return self._config.copy()
    
    def get_system_prompt(self, lang: str = "cn", device_id: Optional[str] = None) -> str:
        """Get system prompt for agent.
        
        Priority: device-specific prompt > global prompt > default prompt
        
        Args:
            lang: Language code, 'cn' for Chinese, 'en' for English.
            device_id: Optional device ID. If provided, will check for device-specific prompt first.
        
        Returns:
            System prompt string.
        """
        # First, check for device-specific prompt if device_id is provided
        if device_id:
            device_prompts = self._config.get("device_system_prompts", {})
            device_prompt = device_prompts.get(device_id, {}).get(lang)
            if device_prompt:
                # Replace date placeholder if present
                from datetime import datetime
                if lang == "cn":
                    today = datetime.today()
                    weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
                    weekday = weekday_names[today.weekday()]
                    formatted_date = today.strftime("%Y年%m月%d日") + " " + weekday
                    if "{date}" in device_prompt:
                        return device_prompt.replace("{date}", formatted_date)
                    if device_prompt.startswith("今天的日期是: "):
                        lines = device_prompt.split("\n", 1)
                        if len(lines) > 1:
                            return f"今天的日期是: {formatted_date}\n{lines[1]}"
                    return device_prompt.replace("{date}", formatted_date)
                else:
                    formatted_date = datetime.today().strftime("%Y-%m-%d, %A")
                    if "{date}" in device_prompt:
                        return device_prompt.replace("{date}", formatted_date)
                    if device_prompt.startswith("The current date: "):
                        lines = device_prompt.split("\n", 1)
                        if len(lines) > 1:
                            return f"The current date: {formatted_date}\n{lines[1]}"
                    return device_prompt.replace("{date}", formatted_date)
        
        # Check if global custom prompt is configured
        custom_prompt = self._config.get("system_prompt", {}).get(lang)
        if custom_prompt:
            # Replace date placeholder if present
            from datetime import datetime
            if lang == "cn":
                today = datetime.today()
                weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
                weekday = weekday_names[today.weekday()]
                formatted_date = today.strftime("%Y年%m月%d日") + " " + weekday
                # Replace {date} placeholder, but also handle the case where date is already in the prompt
                if "{date}" in custom_prompt:
                    return custom_prompt.replace("{date}", formatted_date)
                # If no placeholder, check if it starts with date pattern and replace it
                if custom_prompt.startswith("今天的日期是: "):
                    # Extract the date part and replace
                    lines = custom_prompt.split("\n", 1)
                    if len(lines) > 1:
                        return f"今天的日期是: {formatted_date}\n{lines[1]}"
                return custom_prompt.replace("{date}", formatted_date)
            else:
                formatted_date = datetime.today().strftime("%Y-%m-%d, %A")
                if "{date}" in custom_prompt:
                    return custom_prompt.replace("{date}", formatted_date)
                if custom_prompt.startswith("The current date: "):
                    lines = custom_prompt.split("\n", 1)
                    if len(lines) > 1:
                        return f"The current date: {formatted_date}\n{lines[1]}"
                return custom_prompt.replace("{date}", formatted_date)
        
        # Fallback to default
        from phone_agent.config import get_system_prompt
        return get_system_prompt(lang)
    
    def update_system_prompt(self, prompt: str, lang: str = "cn"):
        """Update system prompt for agent.
        
        Args:
            prompt: System prompt text. Can use {date} placeholder for date.
            lang: Language code, 'cn' for Chinese, 'en' for English.
        """
        if "system_prompt" not in self._config:
            self._config["system_prompt"] = {}
        self._config["system_prompt"][lang] = prompt
        self._save_config()
    
    def reset_system_prompt(self, lang: str = "cn", device_id: Optional[str] = None):
        """Reset system prompt to default.
        
        Args:
            lang: Language code, 'cn' for Chinese, 'en' for English.
            device_id: Optional device ID. If provided, resets device-specific prompt; otherwise resets global prompt.
        """
        if device_id:
            # Reset device-specific prompt
            if "device_system_prompts" in self._config:
                if device_id in self._config["device_system_prompts"]:
                    if lang in self._config["device_system_prompts"][device_id]:
                        del self._config["device_system_prompts"][device_id][lang]
                        # Remove device entry if no prompts left
                        if not self._config["device_system_prompts"][device_id]:
                            del self._config["device_system_prompts"][device_id]
                        self._save_config()
        else:
            # Reset global prompt
            if "system_prompt" in self._config and lang in self._config["system_prompt"]:
                del self._config["system_prompt"][lang]
                self._save_config()
    
    def update_device_system_prompt(self, device_id: str, prompt: str, lang: str = "cn"):
        """Update device-specific system prompt.
        
        Args:
            device_id: Device ID.
            prompt: System prompt text. Can use {date} placeholder for date.
            lang: Language code, 'cn' for Chinese, 'en' for English.
        """
        if "device_system_prompts" not in self._config:
            self._config["device_system_prompts"] = {}
        if device_id not in self._config["device_system_prompts"]:
            self._config["device_system_prompts"][device_id] = {}
        self._config["device_system_prompts"][device_id][lang] = prompt
        self._save_config()
    
    def get_system_prompt_raw(self, lang: str = "cn", device_id: Optional[str] = None) -> tuple[str, bool]:
        """Get raw system prompt (without date replacement) for editing.
        
        Priority: device-specific prompt > global prompt > default prompt
        
        Args:
            lang: Language code, 'cn' for Chinese, 'en' for English.
            device_id: Optional device ID. If provided, will check for device-specific prompt first.
        
        Returns:
            Tuple of (raw prompt string, is_custom bool).
        """
        # First, check for device-specific prompt if device_id is provided
        if device_id:
            device_prompts = self._config.get("device_system_prompts", {})
            device_prompt = device_prompts.get(device_id, {}).get(lang)
            if device_prompt:
                return device_prompt, True
        
        # Check if global custom prompt is configured
        custom_prompt = self._config.get("system_prompt", {}).get(lang)
        if custom_prompt:
            return custom_prompt, True
        
        # Return default prompt (with {date} placeholder for consistency)
        from phone_agent.config import get_system_prompt
        default_prompt = get_system_prompt(lang)
        # Replace the actual date with {date} placeholder for editing
        from datetime import datetime
        if lang == "cn":
            today = datetime.today()
            weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
            weekday = weekday_names[today.weekday()]
            formatted_date = today.strftime("%Y年%m月%d日") + " " + weekday
            if default_prompt.startswith(f"今天的日期是: {formatted_date}"):
                return default_prompt.replace(f"今天的日期是: {formatted_date}", "今天的日期是: {date}", 1), False
        else:
            formatted_date = datetime.today().strftime("%Y-%m-%d, %A")
            if default_prompt.startswith(f"The current date: {formatted_date}"):
                return default_prompt.replace(f"The current date: {formatted_date}", "The current date: {date}", 1), False
        
        return default_prompt, False
        """Get raw system prompt (without date replacement) for editing.
        
        Args:
            lang: Language code, 'cn' for Chinese, 'en' for English.
        
        Returns:
            Raw system prompt string (with {date} placeholder if custom, or default prompt).
        """
        # Check if custom prompt is configured
        custom_prompt = self._config.get("system_prompt", {}).get(lang)
        if custom_prompt:
            return custom_prompt
        
        # Return default prompt (with {date} placeholder for consistency)
        from phone_agent.config import get_system_prompt
        default_prompt = get_system_prompt(lang)
        # Replace the actual date with {date} placeholder for editing
        from datetime import datetime
        if lang == "cn":
            today = datetime.today()
            weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
            weekday = weekday_names[today.weekday()]
            formatted_date = today.strftime("%Y年%m月%d日") + " " + weekday
            if default_prompt.startswith(f"今天的日期是: {formatted_date}"):
                return default_prompt.replace(f"今天的日期是: {formatted_date}", "今天的日期是: {date}", 1)
        else:
            formatted_date = datetime.today().strftime("%Y-%m-%d, %A")
            if default_prompt.startswith(f"The current date: {formatted_date}"):
                return default_prompt.replace(f"The current date: {formatted_date}", "The current date: {date}", 1)
        
        return default_prompt

config_manager = ConfigManager.get_instance()

