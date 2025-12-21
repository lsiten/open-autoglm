"""Utility for matching app names to installed apps using LLM."""

import json
from typing import Any, Optional, Dict, List

from phone_agent.model.client import ModelClient, MessageBuilder

# Default system app mappings (will be overridden by config)
DEFAULT_SYSTEM_APP_MAPPINGS = {
    # App Market / Store
    "应用市场": [
        "com.huawei.appmarket",  # Huawei
        "com.xiaomi.market",  # Xiaomi
        "com.oppo.market",  # OPPO
        "com.vivo.appstore",  # vivo
        "com.samsung.android.apps.samsungapps",  # Samsung
        "com.tencent.android.qqdownloader",  # Tencent App Store
        "com.qihoo.appstore",  # 360 App Store
        "com.baidu.appsearch",  # Baidu App Store
        "com.wandoujia.phoenix2",  # Wandoujia
        "com.yingyonghui.market",  # AppChina
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
    
    # SMS / Messages
    "短信": [
        "com.android.mms",  # Android default
        "com.android.messaging",  # Android Messages
        "com.huawei.mms",  # Huawei
        "com.miui.mms",  # Xiaomi
        "com.coloros.mms",  # OPPO ColorOS
        "com.funtouch.mms",  # vivo Funtouch
        "com.samsung.android.messaging",  # Samsung
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
    
    # Phone / Dialer
    "电话": [
        "com.android.dialer",  # Android default
        "com.android.contacts",  # Sometimes dialer is in contacts
        "com.huawei.contacts",  # Huawei
        "com.miui.dialer",  # Xiaomi
        "com.coloros.dialer",  # OPPO ColorOS
        "com.funtouch.dialer",  # vivo Funtouch
        "com.samsung.android.dialer",  # Samsung
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
    
    # Contacts
    "联系人": [
        "com.android.contacts",  # Android default
        "com.huawei.contacts",  # Huawei
        "com.miui.contacts",  # Xiaomi
        "com.coloros.contacts",  # OPPO ColorOS
        "com.funtouch.contacts",  # vivo Funtouch
        "com.samsung.android.contacts",  # Samsung
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


def match_app_with_llm(
    user_input: str,
    installed_apps: list[dict[str, Any]],
    model_client: ModelClient,
    system_app_mappings: Optional[Dict[str, List[str]]] = None,
    llm_prompt_template: Optional[str] = None,
    action_context: Optional[str] = None,
) -> dict[str, Any]:
    """
    Use LLM to match user input app name to installed apps.
    
    Args:
        user_input: User-provided app name (may be app name, package ID, or description).
        installed_apps: List of installed apps, each with 'name' and 'package' fields.
        model_client: ModelClient instance for LLM requests.
    
    Returns:
        Dictionary with:
        - 'installed': bool - Whether the app is installed
        - 'package_id': str | None - The matched package ID if installed
        - 'app_name': str | None - The matched app name if installed
        - 'reason': str - Explanation of the match result
    """
    if not installed_apps:
        return {
            "installed": False,
            "package_id": None,
            "app_name": None,
            "reason": "No installed apps list provided"
        }
    
    # First, check if it's a known system app
    user_input_lower = user_input.lower().strip()
    installed_packages = {app.get("package", "") for app in installed_apps}
    
    # Detect if this is a system action (send SMS, make call, etc.)
    system_actions = {
        "发短信": ["发短信", "发送短信", "发信息", "发送信息", "发消息", "发送消息", "sms", "mms"],
        "打电话": ["打电话", "拨打电话", "拨号", "呼叫", "call", "dial"],
        "发信息": ["发信息", "发送信息", "发短信", "发送短信"],
        "联系人": ["联系人", "通讯录", "查看联系人", "contacts"],
    }
    
    detected_action = None
    action_keywords = []
    for action_name, keywords in system_actions.items():
        matched_keywords = [kw for kw in keywords if kw.lower() in user_input_lower]
        if matched_keywords:
            detected_action = action_name
            action_keywords = matched_keywords
            break
    
    # Use provided mappings or defaults
    mappings = system_app_mappings if system_app_mappings is not None else DEFAULT_SYSTEM_APP_MAPPINGS
    
    # Always try direct mapping first (more reliable), even for system actions
    # Check system app mappings for both action keywords and user input
    search_keywords = []
    if detected_action:
        # For system actions, search for related keywords in mappings
        if detected_action == "发短信" or detected_action == "发信息":
            search_keywords = ["短信", "信息", "消息", "sms", "mms"]
        elif detected_action == "打电话":
            search_keywords = ["电话", "拨号", "拨打电话", "dialer", "phone"]
        elif detected_action == "联系人":
            search_keywords = ["联系人", "通讯录", "contacts"]
    else:
        # If no action detected, use user input directly
        search_keywords = [user_input_lower]
    
    # Normalize mappings to lowercase keys for easier matching
    normalized_mappings = {k.lower(): v for k, v in mappings.items()}
    
    # Try direct mapping with all relevant keywords
    for keyword in search_keywords:
        keyword_lower = keyword.lower()
        if keyword_lower in normalized_mappings:
            possible_packages = normalized_mappings[keyword_lower]
            # Find which package is actually installed
            for pkg in possible_packages:
                # Handle both old format (list of strings) and new format (list of dicts)
                pkg_name = pkg if isinstance(pkg, str) else pkg.get("package", "")
                if pkg_name in installed_packages:
                    # Find the app name from installed_apps
                    app_name = None
                    for app in installed_apps:
                        if app.get("package") == pkg_name:
                            app_name = app.get("name", pkg_name)
                            break
                    
                    return {
                        "installed": True,
                        "package_id": pkg_name,
                        "app_name": app_name or keyword,
                        "reason": f"Matched system app '{keyword}' to installed package '{pkg_name}'"
                    }
    
    # Also check if user_input directly matches any mapping keyword
    for keyword, possible_packages in normalized_mappings.items():
        if keyword in user_input_lower:
            # Find which package is actually installed
            for pkg in possible_packages:
                # Handle both old format (list of strings) and new format (list of dicts)
                pkg_name = pkg if isinstance(pkg, str) else pkg.get("package", "")
                if pkg_name in installed_packages:
                    # Find the app name from installed_apps
                    app_name = None
                    for app in installed_apps:
                        if app.get("package") == pkg_name:
                            app_name = app.get("name", pkg_name)
                            break
                    
                    return {
                        "installed": True,
                        "package_id": pkg_name,
                        "app_name": app_name or keyword,
                        "reason": f"Matched system app '{keyword}' to installed package '{pkg_name}'"
                    }
    
    # Build prompt for LLM
    apps_list = []
    for app in installed_apps:
        name = app.get("name", "")
        package = app.get("package", "")
        apps_list.append(f"- 名称: {name}, 包名: {package}")
    
    apps_text = "\n".join(apps_list)
    
    # Build system app hints for LLM
    system_app_hints = []
    for keyword, possible_packages in normalized_mappings.items():
        if keyword in user_input_lower:
            # Handle both old format (list of strings) and new format (list of dicts)
            pkg_list = []
            for pkg in possible_packages:
                pkg_name = pkg if isinstance(pkg, str) else pkg.get("package", "")
                if pkg_name in installed_packages:
                    pkg_list.append(pkg_name)
            if pkg_list:
                system_app_hints.append(f"- {keyword}: 可能的包名包括 {', '.join(pkg_list[:3])}")
    
    system_hints_text = "\n".join(system_app_hints) if system_app_hints else "无"
    
    # Add action context if provided
    action_context_text = ""
    if action_context:
        action_context_text = f"\n\n⚠️ 动作上下文: {action_context}"
    elif detected_action:
        action_context_text = f"\n\n⚠️ 重要：检测到用户想要执行系统动作 '{detected_action}'（关键词：{', '.join(action_keywords[:3]) if action_keywords else '无'}）。请优先查找能够执行此动作的系统应用。例如：\n- 发短信/发信息 → 查找短信/信息应用（如 com.android.mms, com.huawei.mms 等）\n- 打电话 → 查找电话/拨号应用（如 com.android.dialer, com.huawei.contacts 等）\n- 联系人 → 查找联系人/通讯录应用（如 com.android.contacts 等）"
    
    # Use provided template or default
    template = llm_prompt_template if llm_prompt_template is not None else """请根据用户输入的应用名称或描述，在已安装应用列表中查找匹配的应用。

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
6. **特别重要**：如果用户输入包含动作描述（如"发短信"、"打电话"、"发信息"），必须找到能够执行该动作的系统应用，而不是其他应用。例如："发短信"应该匹配短信应用，而不是微信或其他应用

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
    
    # Enhance prompt for system actions
    action_instruction = ""
    if detected_action:
        action_instruction = f"\n\n⚠️ 重要提示：用户想要执行系统动作 '{detected_action}'。请优先查找能够执行此动作的系统应用（如短信应用用于发短信，电话应用用于打电话）。如果系统应用提示中有相关应用，请优先匹配。"
    
    prompt = template.format(
        user_input=user_input,
        apps_text=apps_text,
        system_hints_text=system_hints_text
    ) + action_context_text + action_instruction

    try:
        # Create messages for LLM
        messages = [
            MessageBuilder.create_system_message(
                "你是一个应用匹配助手，能够根据用户输入的应用名称或描述，在已安装应用列表中精确匹配对应的应用。"
            ),
            MessageBuilder.create_user_message(prompt)
        ]
        
        # Request from LLM
        response = model_client.request(messages)
        
        # Parse response
        # Extract JSON from response (may contain thinking and action parts)
        # ModelResponse has 'thinking' and 'action' attributes
        if hasattr(response, 'action') and response.action:
            content = response.action
        elif hasattr(response, 'thinking') and response.thinking:
            content = response.thinking
        else:
            content = str(response)
        
        # Try to extract JSON from content
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = content[json_start:json_end]
            result = json.loads(json_str)
            
            # Validate result
            if "installed" in result:
                return {
                    "installed": bool(result.get("installed", False)),
                    "package_id": result.get("package_id"),
                    "app_name": result.get("app_name"),
                    "reason": result.get("reason", "LLM matched")
                }
        
        # Fallback: if JSON parsing fails, return not installed
        return {
            "installed": False,
            "package_id": None,
            "app_name": None,
            "reason": f"Failed to parse LLM response: {content[:100]}"
        }
        
    except Exception as e:
        return {
            "installed": False,
            "package_id": None,
            "app_name": None,
            "reason": f"Error calling LLM: {str(e)}"
        }

