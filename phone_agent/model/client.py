"""Model client for AI inference using OpenAI-compatible API."""

import json
import time
from dataclasses import dataclass, field
from typing import Any
from enum import Enum

from openai import OpenAI

from phone_agent.config.i18n import get_message

try:
    import requests
except ImportError:
    requests = None  # requests might not be available

try:
    import requests
except ImportError:
    requests = None  # requests might not be available


class ModelProvider(Enum):
    """Enumeration of supported model providers."""
    VLLM = "vllm"
    OLLAMA = "ollama"
    BAILIAN = "bailian"  # 阿里云通义千问
    GEMINI = "gemini"  # Google Gemini
    CLAUDE = "claude"  # Anthropic Claude
    OPENAI = "openai"  # OpenAI
    CUSTOM = "custom"  # Custom/Unknown provider


def detect_provider(base_url: str) -> ModelProvider:
    """
    Detect the model provider based on base_url.
    
    Args:
        base_url: The base URL of the API endpoint.
        
    Returns:
        ModelProvider enum value.
    """
    base_url_lower = base_url.lower()
    
    if "generativelanguage.googleapis.com" in base_url_lower or "gemini" in base_url_lower:
        return ModelProvider.GEMINI
    elif "dashscope.aliyuncs.com" in base_url_lower or "bailian" in base_url_lower:
        return ModelProvider.BAILIAN
    elif "api.anthropic.com" in base_url_lower or "claude" in base_url_lower:
        return ModelProvider.CLAUDE
    elif "api.openai.com" in base_url_lower:
        return ModelProvider.OPENAI
    elif "11434" in base_url_lower or "ollama" in base_url_lower:
        return ModelProvider.OLLAMA
    elif "localhost" in base_url_lower or "127.0.0.1" in base_url_lower:
        # Default to VLLM for localhost
        return ModelProvider.VLLM
    else:
        return ModelProvider.CUSTOM


def get_provider_supported_params(provider: ModelProvider) -> dict[str, Any]:
    """
    Get supported parameters for a specific provider.
    
    Args:
        provider: The model provider.
        
    Returns:
        Dictionary with parameter support flags.
    """
    # Default: most parameters supported
    params = {
        "frequency_penalty": True,
        "presence_penalty": True,
        "top_p": True,
        "temperature": True,
        "max_tokens": True,
    }
    
    # Provider-specific overrides
    if provider == ModelProvider.GEMINI:
        # Gemini doesn't support frequency_penalty
        params["frequency_penalty"] = False
        params["presence_penalty"] = False
    elif provider == ModelProvider.BAILIAN:
        # Bailian (通义千问) supports most parameters
        pass
    elif provider == ModelProvider.CLAUDE:
        # Claude API may have different parameter support
        # Note: Claude uses different API format, but if using OpenAI-compatible wrapper, adjust here
        pass
    elif provider == ModelProvider.OLLAMA:
        # Ollama supports most parameters
        pass
    elif provider == ModelProvider.VLLM:
        # VLLM supports all standard parameters
        pass
    
    return params


@dataclass
class ModelConfig:
    """Configuration for the AI model."""

    base_url: str = "http://localhost:8000/v1"
    api_key: str = "EMPTY"
    model_name: str = "autoglm-phone-9b"
    max_tokens: int = 3000
    temperature: float = 0.0
    top_p: float = 0.85
    frequency_penalty: float | None = 0.2  # None to disable (for APIs that don't support it)
    extra_body: dict[str, Any] = field(default_factory=dict)
    lang: str = "cn"  # Language for UI messages: 'cn' or 'en'


@dataclass
class ModelResponse:
    """Response from the AI model."""

    thinking: str
    action: str
    raw_content: str
    # Performance metrics
    time_to_first_token: float | None = None  # Time to first token (seconds)
    time_to_thinking_end: float | None = None  # Time to thinking end (seconds)
    total_time: float | None = None  # Total inference time (seconds)


class ModelClient:
    """
    Client for interacting with OpenAI-compatible vision-language models.

    Args:
        config: Model configuration.
    """

    def __init__(self, config: ModelConfig | None = None):
        self.config = config or ModelConfig()
        # Detect provider based on base_url
        self.provider = detect_provider(self.config.base_url)
        # Get supported parameters for this provider
        self.supported_params = get_provider_supported_params(self.provider)
        # Track if this is a vision language model (for Bailian)
        self.is_vl_model = False
        
        # Normalize API key: treat "EMPTY" as empty string for providers that require API key
        api_key = self.config.api_key
        if api_key == "EMPTY":
            api_key = ""
        
        # For Gemini, validate API key is set (but don't block initialization)
        if self.provider == ModelProvider.GEMINI:
            if not api_key or api_key.strip() == "":
                print(f"Warning: Gemini API requires a valid API key. Please set it in the configuration.")
                print(f"Current api_key value: '{self.config.api_key}' (normalized to empty)")
            else:
                # API key is set, should work fine
                print(f"Gemini API key is set (length: {len(api_key)})")
        
        # For Bailian VL models, ensure compatible-mode endpoint is used
        actual_base_url = self.config.base_url
        if self.provider == ModelProvider.BAILIAN:
            model_name_lower = self.config.model_name.lower()
            is_vl_model_temp = "vl" in model_name_lower or "vision" in model_name_lower
            if is_vl_model_temp:
                # VL models should use compatible-mode endpoint (confirmed by documentation)
                # Check if we need to ensure compatible-mode is used
                if "compatible-mode" not in actual_base_url:
                    # If not using compatible-mode, suggest switching
                    print(f"[Bailian VL Init] Detected VL model: {self.config.model_name}")
                    print(f"[Bailian VL Init] Warning: VL models should use compatible-mode endpoint")
                    print(f"[Bailian VL Init]   Current: {actual_base_url}")
                    print(f"[Bailian VL Init]   Recommended: https://dashscope.aliyuncs.com/compatible-mode/v1")
                else:
                    print(f"[Bailian VL Init] Detected VL model, using compatible-mode endpoint: {actual_base_url}")
        
        # Initialize OpenAI client with normalized API key
        self.client = OpenAI(base_url=actual_base_url, api_key=api_key)

    def request(self, messages: list[dict[str, Any]], on_token: callable = None) -> ModelResponse:
        """
        Send a request to the model.

        Args:
            messages: List of message dictionaries in OpenAI format.
            on_token: Optional callback function for streaming tokens.

        Returns:
            ModelResponse containing thinking and action.
        """
        # Start timing
        start_time = time.time()
        time_to_first_token = None
        time_to_thinking_end = None

        # IMPORTANT: Set is_vl_model early for Bailian, before building request params
        if self.provider == ModelProvider.BAILIAN:
            model_name_lower = self.config.model_name.lower()
            self.is_vl_model = "vl" in model_name_lower or "vision" in model_name_lower
            if self.is_vl_model:
                print(f"[Bailian VL] VL model detected early: {self.config.model_name}")
        
        # Build request parameters based on provider support
        request_params = {
            "messages": messages,
            "model": self.config.model_name,
            "stream": True,
        }
        
        # For Bailian VL models, add stream_options to include usage information
        if self.provider == ModelProvider.BAILIAN and self.is_vl_model:
            request_params["stream_options"] = {"include_usage": True}
            print(f"[Bailian VL] Added stream_options to include usage information")
        
        # Add parameters based on provider support
        if self.supported_params.get("max_tokens", True):
            request_params["max_tokens"] = self.config.max_tokens
        
        if self.supported_params.get("temperature", True):
            request_params["temperature"] = self.config.temperature
        
        if self.supported_params.get("top_p", True):
            request_params["top_p"] = self.config.top_p
        
        # Only include frequency_penalty if provider supports it and it's set
        # For Bailian VL models, exclude frequency_penalty as it may cause issues
        if self.provider == ModelProvider.BAILIAN and self.is_vl_model:
            # VL models may not support frequency_penalty, skip adding it
            print(f"[Bailian VL] Skipping frequency_penalty parameter (not supported by VL models)")
        elif self.supported_params.get("frequency_penalty", False) and self.config.frequency_penalty is not None:
            request_params["frequency_penalty"] = self.config.frequency_penalty
        
        # For Bailian VL models, add stream_options to include usage information
        if self.provider == ModelProvider.BAILIAN and self.is_vl_model:
            request_params["stream_options"] = {"include_usage": True}
            print(f"[Bailian VL] Added stream_options to include usage information")
        
        # Add extra_body if provided
        if self.config.extra_body:
            request_params["extra_body"] = self.config.extra_body
        
        # IMPORTANT: Set is_vl_model early for Bailian, before image detection code
        if self.provider == ModelProvider.BAILIAN:
            model_name_lower = self.config.model_name.lower()
            self.is_vl_model = "vl" in model_name_lower or "vision" in model_name_lower
            if self.is_vl_model:
                print(f"[Bailian VL] VL model detected early: {self.config.model_name}")
        
        # Bailian VL model specific adjustments - add enable_thinking if needed
        if self.provider == ModelProvider.BAILIAN and self.is_vl_model:
            # For VL models, enable thinking process for better responses (as per official example)
            # Check if extra_body already exists
            if "extra_body" not in request_params:
                request_params["extra_body"] = {}
            # Add enable_thinking and thinking_budget if not already set
            if "enable_thinking" not in request_params["extra_body"]:
                request_params["extra_body"]["enable_thinking"] = True
                request_params["extra_body"]["thinking_budget"] = 81920  # Default thinking budget from official example
                print(f"[Bailian VL] Added enable_thinking=True and thinking_budget=81920 for VL model")
            
            # Check image sizes - Bailian has 10MB limit per image
            for msg in messages:
                if isinstance(msg.get("content"), list):
                    for item in msg.get("content", []):
                        if isinstance(item, dict) and item.get("type") == "image_url":
                            url = item.get("image_url", {}).get("url", "")
                            if url.startswith("data:image"):
                                # Extract base64 part
                                if "," in url:
                                    base64_part = url.split(",", 1)[1]
                                    # Approximate size: base64 is ~4/3 of original size
                                    # But we check the base64 string length directly
                                    base64_size_bytes = len(base64_part) * 3 // 4  # Approximate
                                    base64_size_mb = base64_size_bytes / (1024 * 1024)
                                    if base64_size_mb > 10:
                                        print(f"[Bailian VL] ⚠️ Warning: Image size ({base64_size_mb:.2f}MB) exceeds 10MB limit!")
                                    else:
                                        print(f"[Bailian VL] Image size: {base64_size_mb:.2f}MB (within 10MB limit)")
        
        # Bailian VL model specific adjustments
        if self.provider == ModelProvider.BAILIAN and self.is_vl_model:
            # For Bailian VL models, ensure proper image format handling
            # The compatible-mode endpoint should handle images automatically
            # Check if messages contain images for debugging
            has_images = any(
                isinstance(msg.get("content"), list) and any(
                    isinstance(item, dict) and item.get("type") == "image_url"
                    for item in msg.get("content", [])
                )
                for msg in messages
            )
            if has_images:
                print(f"[Bailian VL] Detected images in messages, VL model should process them correctly")
                # Count images and check format
                image_count = 0
                for msg in messages:
                    if isinstance(msg.get("content"), list):
                        for item in msg.get("content", []):
                            if isinstance(item, dict) and item.get("type") == "image_url":
                                image_count += 1
                                image_url = item.get("image_url", {}).get("url", "")
                                if image_url:
                                    if "data:image/jpeg" in image_url or "data:image/jpg" in image_url:
                                        print(f"[Bailian VL] Image {image_count}: JPEG format (correct for screenshots)")
                                    elif "data:image/png" in image_url:
                                        print(f"[Bailian VL] Image {image_count}: PNG format")
                                    else:
                                        print(f"[Bailian VL] Image {image_count}: Format - {image_url[:80]}")
                print(f"[Bailian VL] Total images in request: {image_count}")
            else:
                print(f"[Bailian VL] Warning: No images detected in messages for VL model")
                print(f"[Bailian VL] This may cause the model to return empty responses")
            
            # Log request parameters for debugging
            print(f"[Bailian VL] Request model: {request_params.get('model')}")
            print(f"[Bailian VL] Request has {len(messages)} messages")
            print(f"[Bailian VL] Endpoint: {self.config.base_url}")
            
            # Detailed message inspection
            print(f"[Bailian VL] About to send request with {len(messages)} messages")
            for i, msg in enumerate(messages):
                msg_role = msg.get("role", "unknown")
                msg_content = msg.get("content", "")
                if isinstance(msg_content, list):
                    print(f"[Bailian VL] Message {i} ({msg_role}): {len(msg_content)} content items")
                    for j, item in enumerate(msg_content):
                        if isinstance(item, dict):
                            item_type = item.get("type", "unknown")
                            if item_type == "image_url":
                                url = item.get("image_url", {}).get("url", "")
                                url_preview = url[:100] + "..." if len(url) > 100 else url
                                print(f"[Bailian VL]   Item {j}: image_url (length: {len(url)} chars, preview: {url_preview})")
                            elif item_type == "text":
                                text = item.get("text", "")
                                text_preview = text[:100] + "..." if len(text) > 100 else text
                                print(f"[Bailian VL]   Item {j}: text (length: {len(text)} chars, preview: {text_preview})")
                            else:
                                print(f"[Bailian VL]   Item {j}: {item_type}")
                else:
                    content_preview = str(msg_content)[:100] + "..." if len(str(msg_content)) > 100 else str(msg_content)
                    print(f"[Bailian VL] Message {i} ({msg_role}): {type(msg_content)} (length: {len(str(msg_content))}, preview: {content_preview})")
        
        # Provider-specific adjustments
        if self.provider == ModelProvider.GEMINI:
            # Gemini requires API key - check if it's set
            api_key = self.config.api_key if self.config.api_key != "EMPTY" else ""
            if not api_key or api_key.strip() == "":
                raise ValueError(
                    "Gemini API requires a valid API key. "
                    "Please set it in the configuration. "
                    "You can get an API key from https://makersuite.google.com/app/apikey"
                )
            
            # Log endpoint and model for debugging
            print(f"[Gemini Debug] Endpoint: {self.config.base_url}")
            print(f"[Gemini Debug] Model: {self.config.model_name}")
            print(f"[Gemini Debug] API key length: {len(api_key)}")
        
        elif self.provider == ModelProvider.BAILIAN:
            # Bailian (百炼) requires API key - check if it's set
            api_key = self.config.api_key if self.config.api_key != "EMPTY" else ""
            if not api_key or api_key.strip() == "":
                raise ValueError(
                    "百炼 API 需要有效的 API Key。"
                    "请在配置中设置 API Key。"
                    "您可以从 https://bailian.console.aliyun.com 获取 API Key"
                )
            
            # Log endpoint and model for debugging
            print(f"[Bailian Debug] Endpoint: {self.config.base_url}")
            print(f"[Bailian Debug] Model: {self.config.model_name}")
            print(f"[Bailian Debug] API key length: {len(api_key)}")
            
            # is_vl_model should already be set earlier, but verify here
            if not hasattr(self, 'is_vl_model') or self.is_vl_model is None:
                model_name_lower = self.config.model_name.lower()
                self.is_vl_model = "vl" in model_name_lower or "vision" in model_name_lower
            
            if self.is_vl_model:
                print(f"[Bailian Debug] Visual language model confirmed ({self.config.model_name})")
                print(f"[Bailian Debug] VL models are supported via compatible-mode endpoint")
                print(f"[Bailian Debug] Ensure images are properly formatted in messages")
        
        # Debug: Force print for Bailian VL before sending request
        if self.provider == ModelProvider.BAILIAN and self.is_vl_model:
            print(f"[Bailian VL] ===== PRE-REQUEST DEBUG =====")
            print(f"[Bailian VL] About to send request with {len(messages)} messages")
            for i, msg in enumerate(messages):
                msg_role = msg.get("role", "unknown")
                msg_content = msg.get("content", "")
                if isinstance(msg_content, list):
                    print(f"[Bailian VL] Message {i} ({msg_role}): {len(msg_content)} content items")
                    for j, item in enumerate(msg_content):
                        if isinstance(item, dict):
                            item_type = item.get("type", "unknown")
                            if item_type == "image_url":
                                url = item.get("image_url", {}).get("url", "")
                                print(f"[Bailian VL]   Item {j}: image_url (length: {len(url)} chars)")
                                print(f"[Bailian VL]     URL starts with: {url[:50] if url else 'EMPTY'}")
                            elif item_type == "text":
                                text = item.get("text", "")
                                print(f"[Bailian VL]   Item {j}: text (length: {len(text)} chars)")
                else:
                    print(f"[Bailian VL] Message {i} ({msg_role}): {type(msg_content).__name__} (not a list!)")
            print(f"[Bailian VL] ===== END PRE-REQUEST DEBUG =====")
        
        # Try to create the stream
        try:
            # Debug: Log request params for Bailian VL
            if self.provider == ModelProvider.BAILIAN and self.is_vl_model:
                print(f"[Bailian VL] Request params keys: {list(request_params.keys())}")
                print(f"[Bailian VL] Model: {request_params.get('model')}")
                print(f"[Bailian VL] Stream: {request_params.get('stream')}")
                print(f"[Bailian VL] Max tokens: {request_params.get('max_tokens')}")
                print(f"[Bailian VL] Temperature: {request_params.get('temperature')}")
                if request_params.get('extra_body'):
                    print(f"[Bailian VL] Extra body: {request_params.get('extra_body')}")
            
            stream = self.client.chat.completions.create(**request_params)
        except Exception as e:
            # Handle provider-specific errors
            error_str = str(e).lower()
            
            # For Gemini, if model not found, try fallback models
            if self.provider == ModelProvider.GEMINI and "not found" in error_str and "model" in error_str:
                # Try fallback models in order: gemini-3-flash -> gemini-1.5-flash -> gemini-1.5-pro
                fallback_models = []
                original_model = self.config.model_name
                if "gemini-3" in original_model.lower():
                    fallback_models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
                elif "gemini-1.5-flash" in original_model.lower():
                    fallback_models = ["gemini-1.5-pro", "gemini-pro"]
                elif "gemini-1.5-pro" in original_model.lower():
                    fallback_models = ["gemini-pro"]
                else:
                    # For any other model, try common fallbacks
                    fallback_models = ["gemini-pro"]
                    # For any other model, try common fallbacks
                    fallback_models = ["gemini-pro"]
                
                last_error = e
                for fallback_model in fallback_models:
                    try:
                        print(f"Warning: Model {original_model} not found, trying fallback: {fallback_model}")
                        # Create a new request_params with the fallback model
                        fallback_params = request_params.copy()
                        fallback_params["model"] = fallback_model
                        stream = self.client.chat.completions.create(**fallback_params)
                        print(f"Successfully using fallback model: {fallback_model}")
                        # Update config for future requests (optional, but helpful)
                        self.config.model_name = fallback_model
                        break
                    except Exception as fallback_error:
                        last_error = fallback_error
                        error_str_fallback = str(fallback_error).lower()
                        if "not found" in error_str_fallback and "model" in error_str_fallback:
                            print(f"Fallback model {fallback_model} also not found, trying next...")
                            continue
                        else:
                            # Different error, might be API key or other issue
                            print(f"Error with fallback model {fallback_model}: {fallback_error}")
                            continue
                else:
                    # All fallbacks failed, try to query available models using ListModels API
                    available_models = []
                    try:
                        # Try to call ListModels API to get available models
                        # For OpenAI-compatible endpoint, we need to use native Gemini API
                        print("Attempting to query available models from Gemini API...")
                        
                        # Try to use the models.list endpoint
                        if requests is not None:
                            api_key = self.config.api_key if self.config.api_key != "EMPTY" else ""
                            if api_key:
                                # Use the native Gemini API endpoint for listing models
                                list_url = "https://generativelanguage.googleapis.com/v1beta/models"
                                headers = {"x-goog-api-key": api_key}
                                response = requests.get(list_url, headers=headers, timeout=5)
                                if response.status_code == 200:
                                    models_data = response.json()
                                    if "models" in models_data:
                                        available_models = [m.get("name", "") for m in models_data["models"]]
                                        print(f"Found {len(available_models)} available models from API")
                                        # Filter and format model names (remove 'models/' prefix if present)
                                        available_models = [m.replace("models/", "") for m in available_models if m]
                                        # Remove duplicates and sort
                                        available_models = sorted(list(set(available_models)))
                                elif response.status_code == 401:
                                    print("API key authentication failed when listing models")
                                else:
                                    print(f"Could not list models: HTTP {response.status_code} - {response.text[:200]}")
                            else:
                                print("No API key available to query models")
                        else:
                            print("requests library not available, cannot query models")
                    except Exception as list_error:
                        print(f"Could not query available models: {list_error}")
                    
                    # All fallbacks failed, raise error with helpful message
                    error_msg = f"Model not found: {original_model}"
                    if fallback_models:
                        error_msg += f" (tried fallbacks: {', '.join(fallback_models)})"
                    error_msg += f"\n\nError details: {str(last_error)}"
                    
                    if available_models:
                        error_msg += f"\n\n✅ Found {len(available_models)} available models from Gemini API:"
                        for model in available_models[:15]:  # Show first 15
                            error_msg += f"\n  - {model}"
                        if len(available_models) > 15:
                            error_msg += f"\n  ... and {len(available_models) - 15} more"
                        error_msg += "\n\nPlease update your configuration to use one of these model names."
                    else:
                        error_msg += (
                            "\n\nPossible issues and solutions:"
                            "\n1. API Endpoint: The endpoint might need to be different."
                            "\n   Current: https://generativelanguage.googleapis.com/v1beta/openai/"
                            "\n   Try alternative endpoints:"
                            "\n   - https://generativelanguage.googleapis.com/v1beta"
                            "\n   - https://generativelanguage.googleapis.com/v1"
                            "\n2. Model Name Format: Model names might need different format."
                            "\n   Try: 'models/gemini-pro' instead of 'gemini-pro'"
                            "\n   Or check Google AI Studio for exact model identifiers"
                            "\n3. API Key: Verify your API key is valid and has proper permissions"
                            "\n4. Region: Some models may not be available in your region"
                            "\n\nTo find available models:"
                            "\n- Visit https://aistudio.google.com and check available models"
                            "\n- Or use Google Cloud Console to list models via API"
                            "\n- Check the exact model identifier format required"
                        )
                    raise ValueError(error_msg) from last_error
            
            # Check for model not found errors (for other providers or if fallback already handled)
            elif "not found" in error_str and "model" in error_str:
                error_msg = f"Model not found: {self.config.model_name}\n{str(e)}"
                if self.provider == ModelProvider.GEMINI:
                    error_msg += (
                        "\n\nAvailable Gemini model names (latest):"
                        "\n  - gemini-3-flash (latest, fast and efficient)"
                        "\n  - gemini-3-pro (latest, more capable)"
                        "\n  - gemini-1.5-flash (stable, fast and efficient)"
                        "\n  - gemini-1.5-pro (stable, more capable)"
                        "\n  - gemini-2.0-flash-exp (experimental)"
                        "\n  - gemini-pro (legacy)"
                        "\n\nNote: Model names may vary by API version and region."
                        "\nIf gemini-3-* models are not available, try gemini-1.5-flash or gemini-1.5-pro"
                        "\nPlease check Google AI Studio (https://aistudio.google.com) for the latest available models."
                    )
                elif self.provider == ModelProvider.BAILIAN:
                    error_msg += (
                        "\n\n百炼平台模型名称参考："
                        "\n文本模型："
                        "\n  - qwen-plus (推荐，性价比高)"
                        "\n  - qwen-max (更强能力)"
                        "\n  - qwen-turbo (快速响应)"
                        "\n视觉语言模型："
                        "\n  - qwen-vl-plus (视觉理解)"
                        "\n  - qwen-vl-max (更强视觉能力)"
                        "\n  - qwen3-vl-plus (最新视觉模型，需要确认可用性)"
                        "\n\n排查步骤："
                        "\n1. 确认模型名称是否正确（区分大小写）"
                        "\n2. 检查 API Key 是否有权限访问该模型"
                        "\n3. 登录百炼控制台查看模型可用性：https://bailian.console.aliyun.com"
                        "\n4. 确认端点配置是否正确："
                        "\n   - 文本模型：https://dashscope.aliyuncs.com/compatible-mode/v1"
                        "\n   - 视觉模型可能需要不同的端点"
                        "\n5. 如果使用 qwen3-vl-plus，可能需要："
                        "\n   - 确认模型已发布并可用"
                        "\n   - 检查是否需要特殊订阅或权限"
                        "\n   - 尝试使用 qwen-vl-plus 作为替代"
                    )
                raise ValueError(error_msg) from e
            
            # Check for frequency_penalty errors (fallback for unknown providers)
            if "frequency_penalty" in error_str and ("unknown" in error_str or "cannot find field" in error_str):
                print(f"Warning: API doesn't support frequency_penalty parameter, retrying without it...")
                request_params.pop("frequency_penalty", None)
                stream = self.client.chat.completions.create(**request_params)
            # Check for authorization errors (e.g., Gemini, Bailian)
            elif "authorization" in error_str or "missing authorization" in error_str or "unauthorized" in error_str:
                error_msg = f"Authorization error: {str(e)}"
                if self.provider == ModelProvider.GEMINI:
                    error_msg += (
                        "\nGemini API requires a valid API key. "
                        "Please check your configuration and ensure the API key is set correctly. "
                        "You can get an API key from https://makersuite.google.com/app/apikey"
                    )
                elif self.provider == ModelProvider.BAILIAN:
                    error_msg += (
                        "\n百炼 API 需要有效的 API Key。"
                        "\n请检查配置并确保 API Key 设置正确。"
                        "\n您可以从以下地址获取 API Key："
                        "\n  - https://bailian.console.aliyun.com"
                        "\n  - 或访问阿里云控制台 > 百炼 > API Key 管理"
                        "\n\n常见问题："
                        "\n1. API Key 未设置或已过期"
                        "\n2. API Key 没有访问该模型的权限"
                        "\n3. 账户余额不足或未开通服务"
                    )
                raise ValueError(error_msg) from e
            else:
                # Re-raise if it's a different error
                raise

        raw_content = ""
        reasoning_content = ""  # For VL models with enable_thinking
        buffer = ""  # Buffer to hold content that might be part of a marker
        action_markers = ["finish(message=", "do(action="]
        in_action_phase = False  # Track if we've entered the action phase
        first_token_received = False
        chunk_count = 0

        for chunk in stream:
            chunk_count += 1
            # Debug: Log first few chunks for Bailian VL, and also the last chunk (with finish_reason)
            is_last_chunk = False
            if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                if hasattr(chunk.choices[0], 'finish_reason') and chunk.choices[0].finish_reason:
                    is_last_chunk = True
            
            should_log_chunk = (
                (self.provider == ModelProvider.BAILIAN and self.is_vl_model and chunk_count <= 5) or
                (self.provider == ModelProvider.BAILIAN and self.is_vl_model and is_last_chunk)
            )
            
            if should_log_chunk:
                print(f"[Bailian VL] Chunk {chunk_count}: choices={len(chunk.choices) if hasattr(chunk, 'choices') else 'N/A'}")
                if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                    choice = chunk.choices[0]
                    if hasattr(choice, 'delta'):
                        delta = choice.delta
                        delta_content = getattr(delta, 'content', None)
                        delta_role = getattr(delta, 'role', None)
                        print(f"[Bailian VL]   Delta content: {delta_content!r}")
                        print(f"[Bailian VL]   Delta role: {delta_role}")
                        # Check for refusal
                        if hasattr(delta, 'refusal') and delta.refusal:
                            print(f"[Bailian VL]   ⚠️ Refusal: {delta.refusal}")
                    if hasattr(choice, 'finish_reason'):
                        print(f"[Bailian VL]   Finish reason: {choice.finish_reason}")
                # Check for errors
                if hasattr(chunk, 'error'):
                    print(f"[Bailian VL]   ⚠️ Error in chunk: {chunk.error}")
                # Try to get chunk as dict for more info
                try:
                    if hasattr(chunk, 'model_dump'):
                        chunk_dict = chunk.model_dump()
                        # Always check usage in the last chunk (with finish_reason), or first few chunks
                        if chunk_dict and (chunk_count <= 2 or is_last_chunk):
                            print(f"[Bailian VL]   Chunk dict keys: {list(chunk_dict.keys())}")
                            # Check for usage information (even if it's None or empty)
                            if 'usage' in chunk_dict:
                                usage = chunk_dict['usage']
                                if usage:
                                    print(f"[Bailian VL]   Usage - Prompt tokens: {usage.get('prompt_tokens', 'N/A')}, "
                                          f"Completion tokens: {usage.get('completion_tokens', 'N/A')}, "
                                          f"Total tokens: {usage.get('total_tokens', 'N/A')}")
                                    # If prompt tokens > 0 but completion tokens = 0, this indicates model refusal
                                    prompt_tokens = usage.get('prompt_tokens', 0)
                                    completion_tokens = usage.get('completion_tokens', 0)
                                    if prompt_tokens > 0 and completion_tokens == 0:
                                        print(f"[Bailian VL]   ⚠️ Warning: Model processed {prompt_tokens} prompt tokens but returned 0 completion tokens")
                                        print(f"[Bailian VL]   This strongly suggests model refusal or content policy violation")
                                else:
                                    print(f"[Bailian VL]   Usage field exists but is None or empty: {usage}")
                            else:
                                print(f"[Bailian VL]   No 'usage' field in chunk_dict")
                            # Check for any error or warning fields
                            for key in ['error', 'warning', 'message', 'code']:
                                if key in chunk_dict:
                                    print(f"[Bailian VL]   ⚠️ {key}: {chunk_dict[key]}")
                except Exception as e:
                    if self.provider == ModelProvider.BAILIAN and self.is_vl_model:
                        print(f"[Bailian VL]   Error getting chunk dict: {e}")
            if len(chunk.choices) == 0:
                # This is likely the usage chunk (when stream_options={"include_usage": True})
                # As per official example: "如果chunk.choices为空，则打印usage"
                if self.provider == ModelProvider.BAILIAN and self.is_vl_model:
                    if hasattr(chunk, 'usage') and chunk.usage:
                        usage = chunk.usage
                        prompt_tokens = getattr(usage, 'prompt_tokens', None)
                        completion_tokens = getattr(usage, 'completion_tokens', None)
                        total_tokens = getattr(usage, 'total_tokens', None)
                        print(f"[Bailian VL] Usage chunk - Prompt tokens: {prompt_tokens}, "
                              f"Completion tokens: {completion_tokens}, "
                              f"Total tokens: {total_tokens}")
                        if prompt_tokens and prompt_tokens > 0 and (completion_tokens is None or completion_tokens == 0):
                            print(f"[Bailian VL] ⚠️ Warning: Model processed {prompt_tokens} prompt tokens but returned 0 completion tokens")
                            print(f"[Bailian VL] This strongly suggests model refusal or content policy violation")
                    else:
                        print(f"[Bailian VL] Empty chunk.choices but no usage information found")
                        if hasattr(chunk, 'error'):
                            print(f"[Bailian VL] Error in chunk: {chunk.error}")
                continue
            # Get content from delta (may be None)
            # For VL models with enable_thinking, check reasoning_content first
            content = None
            reasoning_chunk = None
            content_to_process = None
            
            delta = chunk.choices[0].delta
            
            # Check for reasoning_content (thinking process) - for VL models with enable_thinking
            if self.provider == ModelProvider.BAILIAN and self.is_vl_model:
                if hasattr(delta, 'reasoning_content') and delta.reasoning_content is not None:
                    reasoning_chunk = delta.reasoning_content
                    reasoning_content += reasoning_chunk
                    raw_content += reasoning_chunk
                    content_to_process = reasoning_chunk  # Use reasoning_content for processing
                    if chunk_count <= 3:  # Only log first few chunks
                        print(f"[Bailian VL] Reasoning content chunk: {reasoning_chunk[:50]}..." if len(reasoning_chunk) > 50 else f"[Bailian VL] Reasoning content chunk: {reasoning_chunk}")
            
            # Check for regular content
            if delta.content is not None:
                content = delta.content
                print(f"DEBUG_CHUNK: {content!r}")
                raw_content += content
                content_to_process = content  # Use regular content for processing
            elif self.provider == ModelProvider.BAILIAN and self.is_vl_model:
                # For Bailian VL models, log chunk details for debugging
                # delta is already defined above
                if hasattr(delta, 'role') and delta.role:
                    print(f"[Bailian VL] Chunk role: {delta.role}")
                if hasattr(chunk.choices[0], 'finish_reason') and chunk.choices[0].finish_reason:
                    print(f"[Bailian VL] Finish reason: {chunk.choices[0].finish_reason}")
                # Check for refusal (model refusing to respond) - this is important for Bailian
                if hasattr(delta, 'refusal') and delta.refusal:
                    print(f"[Bailian VL] ⚠️ Model refusal detected: {delta.refusal}")
                    print(f"[Bailian VL] This may indicate content policy violation or model safety filter")
                # Check for tool_calls (if model wants to call tools)
                if hasattr(delta, 'tool_calls') and delta.tool_calls:
                    print(f"[Bailian VL] Tool calls detected: {delta.tool_calls}")
                # Check for errors in chunk
                if hasattr(chunk, 'error'):
                    print(f"[Bailian VL] Error in chunk: {chunk.error}")
                # Log delta content status (only once per chunk, not repeatedly)
                if hasattr(delta, 'content'):
                    if delta.content is None:
                        # Only log this once per chunk, not for every iteration
                        if chunk_count <= 3:  # Only log first few chunks
                            print(f"[Bailian VL] Delta content is None (empty response)")
                    elif delta.content == "":
                        if chunk_count <= 3:  # Only log first few chunks
                            print(f"[Bailian VL] Delta content is empty string")
                
                # Check usage information if available
                if hasattr(chunk, 'usage') and chunk.usage:
                    usage = chunk.usage
                    prompt_tokens = getattr(usage, 'prompt_tokens', None)
                    completion_tokens = getattr(usage, 'completion_tokens', None)
                    total_tokens = getattr(usage, 'total_tokens', None)
                    print(f"[Bailian VL] Usage - Prompt tokens: {prompt_tokens}, "
                          f"Completion tokens: {completion_tokens}, "
                          f"Total tokens: {total_tokens}")
                    if prompt_tokens and prompt_tokens > 0 and (completion_tokens is None or completion_tokens == 0):
                        print(f"[Bailian VL] ⚠️ Warning: Model processed prompt ({prompt_tokens} tokens) but returned no content")
                        print(f"[Bailian VL] This may indicate model refusal, content policy violation, or model unavailability")
            
            # Process content or reasoning_content
            # content_to_process is set above (either content or reasoning_chunk)
            if content_to_process is not None:
                # Record time to first token
                if not first_token_received:
                    time_to_first_token = time.time() - start_time
                    first_token_received = True

                if in_action_phase:
                    # Already in action phase, just accumulate content without printing
                    continue

                buffer += content_to_process

                # Check if any marker is fully present in buffer
                marker_found = False
                for marker in action_markers:
                    if marker in buffer:
                        # Marker found, print everything before it
                        thinking_part = buffer.split(marker, 1)[0]
                        print(thinking_part, end="", flush=True)
                        if on_token:
                            on_token(thinking_part)
                        print()  # Print newline after thinking is complete
                        if on_token:
                            on_token("\n")
                        in_action_phase = True
                        marker_found = True

                        # Record time to thinking end
                        if time_to_thinking_end is None:
                            time_to_thinking_end = time.time() - start_time

                        break

                if marker_found:
                    continue  # Continue to collect remaining content

                # Check if buffer ends with a prefix of any marker
                # If so, don't print yet (wait for more content)
                is_potential_marker = False
                for marker in action_markers:
                    for i in range(1, len(marker)):
                        if buffer.endswith(marker[:i]):
                            is_potential_marker = True
                            break
                    if is_potential_marker:
                        break

                if not is_potential_marker:
                    # Safe to print the buffer
                    print(buffer, end="", flush=True)
                    if on_token:
                        on_token(buffer)
                    buffer = ""

        # Calculate total time
        total_time = time.time() - start_time

        # Log raw content for debugging (especially for Bailian VL models)
        if self.provider == ModelProvider.BAILIAN and self.is_vl_model:
            print(f"[Bailian VL] Raw response length: {len(raw_content)}")
            if not raw_content or raw_content.strip() == "":
                print(f"[Bailian VL] ⚠️ Warning: Empty response from model")
                print(f"[Bailian VL] This may indicate:")
                print(f"[Bailian VL]   1. Model name '{self.config.model_name}' may not be available or correct")
                print(f"[Bailian VL]      - Try using 'qwen-vl-plus' instead of 'qwen3-vl-plus'")
                print(f"[Bailian VL]      - Check Bailian console to confirm model availability")
                print(f"[Bailian VL]   2. API Key may not have permission to access this model")
                print(f"[Bailian VL]      - Verify API Key permissions in Bailian console")
                print(f"[Bailian VL]   3. Image format issue (e.g., size, encoding, MIME type)")
                print(f"[Bailian VL]   4. Model quota or rate limit exceeded")
                print(f"[Bailian VL]   5. Model refusal (content policy violation)")
                print(f"[Bailian VL] Note: Usage field was None in all chunks, suggesting model did not process the request")
            else:
                print(f"[Bailian VL] Raw response preview (first 200 chars): {raw_content[:200]}")

        # Parse thinking and action from response
        thinking, action = self._parse_response(raw_content)

        # Print performance metrics
        lang = self.config.lang
        print()
        print("=" * 50)
        print(f"⏱️  {get_message('performance_metrics', lang)}:")
        print("-" * 50)
        if time_to_first_token is not None:
            print(
                f"{get_message('time_to_first_token', lang)}: {time_to_first_token:.3f}s"
            )
        if time_to_thinking_end is not None:
            print(
                f"{get_message('time_to_thinking_end', lang)}:        {time_to_thinking_end:.3f}s"
            )
        print(
            f"{get_message('total_inference_time', lang)}:          {total_time:.3f}s"
        )
        print("=" * 50)

        return ModelResponse(
            thinking=thinking,
            action=action,
            raw_content=raw_content,
            time_to_first_token=time_to_first_token,
            time_to_thinking_end=time_to_thinking_end,
            total_time=total_time,
        )

    def _parse_response(self, content: str) -> tuple[str, str]:
        """
        Parse the model response into thinking and action parts.

        Parsing rules:
        1. If content contains 'finish(message=', everything before is thinking,
           everything from 'finish(message=' onwards is action.
        2. If rule 1 doesn't apply but content contains 'do(action=',
           everything before is thinking, everything from 'do(action=' onwards is action.
        3. Fallback: If content contains '<answer>', use legacy parsing with XML tags.
        4. Otherwise, return empty thinking and full content as action.

        Args:
            content: Raw response content.

        Returns:
            Tuple of (thinking, action).
        """
        # Rule 1: Check for finish(message=
        if "finish(message=" in content:
            parts = content.split("finish(message=", 1)
            thinking = parts[0].strip()
            action = "finish(message=" + parts[1]
            return thinking, action

        # Rule 2: Check for do(action=
        if "do(action=" in content:
            parts = content.split("do(action=", 1)
            thinking = parts[0].strip()
            action = "do(action=" + parts[1]
            return thinking, action

        # Rule 3: Fallback to legacy XML tag parsing
        if "<answer>" in content:
            parts = content.split("<answer>", 1)
            thinking = parts[0].replace("<think>", "").replace("</think>", "").strip()
            action = parts[1].replace("</answer>", "").strip()
            return thinking, action

        # Rule 4: No markers found, return content as action
        # If content is empty, return a default finish action
        if not content or content.strip() == "":
            return "", "finish(message=\"模型返回了空响应\")"
        return "", content


class MessageBuilder:
    """Helper class for building conversation messages."""

    @staticmethod
    def create_system_message(content: str) -> dict[str, Any]:
        """Create a system message."""
        return {"role": "system", "content": content}

    @staticmethod
    def create_user_message(
        text: str, image_base64: str | None = None, image_format: str = "jpeg"
    ) -> dict[str, Any]:
        """
        Create a user message with optional image.

        Args:
            text: Text content.
            image_base64: Optional base64-encoded image.
            image_format: Image format ("jpeg", "png", etc.). Defaults to "jpeg".

        Returns:
            Message dictionary.
        """
        content = []

        if image_base64:
            # Use correct MIME type based on image format
            # Most screenshots are JPEG, but allow override
            mime_type = f"image/{image_format}"
            image_url = f"data:{mime_type};base64,{image_base64}"
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": image_url},
                }
            )
            # Debug: Log image info (always log for debugging)
            print(f"[MessageBuilder] ✅ Added image to message: format={image_format}, base64_length={len(image_base64)}, url_length={len(image_url)}")
            print(f"[MessageBuilder] Image URL preview: {image_url[:150]}...")
        else:
            print(f"[MessageBuilder] ⚠️ Warning: No image_base64 provided for user message")

        content.append({"type": "text", "text": text})

        return {"role": "user", "content": content}

    @staticmethod
    def create_assistant_message(content: str) -> dict[str, Any]:
        """Create an assistant message."""
        return {"role": "assistant", "content": content}

    @staticmethod
    def remove_images_from_message(message: dict[str, Any]) -> dict[str, Any]:
        """
        Remove image content from a message to save context space.

        Args:
            message: Message dictionary.

        Returns:
            Message with images removed.
        """
        if isinstance(message.get("content"), list):
            message["content"] = [
                item for item in message["content"] if item.get("type") == "text"
            ]
        return message

    @staticmethod
    def build_screen_info(current_app: str, **extra_info) -> str:
        """
        Build screen info string for the model.

        Args:
            current_app: Current app name.
            **extra_info: Additional info to include.

        Returns:
            JSON string with screen info.
        """
        info = {"current_app": current_app, **extra_info}
        return json.dumps(info, ensure_ascii=False)
    
    @staticmethod
    def build_recordings_info(recordings: list[dict]) -> str:
        """
        Build recordings info string for the model.
        
        Args:
            recordings: List of recording dictionaries with id, name, keywords, description, action_count.
        
        Returns:
            Formatted string with available recordings.
        """
        if not recordings:
            return ""
        
        lines = ["** 可用的录制动作 **"]
        for rec in recordings:
            lines.append(f"- {rec['name']} (ID: {rec['id']})")
            if rec.get('keywords'):
                lines.append(f"  关键字: {', '.join(rec['keywords'])}")
            if rec.get('description'):
                lines.append(f"  描述: {rec['description']}")
            lines.append(f"  动作数: {rec.get('action_count', 0)}")
            lines.append("")
        
        lines.append("如果任务匹配某个录制的关键字，可以使用 ExecuteRecording 操作执行该录制。")
        return "\n".join(lines)