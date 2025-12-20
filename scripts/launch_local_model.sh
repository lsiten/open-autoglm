#!/bin/bash

# Check if vllm is installed
if ! command -v vllm &> /dev/null; then
    echo "Error: vllm is not installed."
    echo "Please install it using: pip install vllm"
    exit 1
fi

# Use ModelScope for faster download in China
export VLLM_USE_MODELSCOPE=True

echo "Starting autoglm-phone-9b on port 8080..."
echo "Model: ZhipuAI/AutoGLM-Phone-9B (ModelScope)"
echo "Note: This requires a GPU with sufficient VRAM (approx 24GB for fp16, less for quantized)."

# Launch vLLM
# --trust-remote-code is often needed for GLM models
# --host 0.0.0.0 allows access from other machines (optional, but good for local network)
# --port 8000 is the default, explicitly setting it here.

vllm serve ZhipuAI/AutoGLM-Phone-9B \
    --served-model-name autoglm-phone-9b \
    --port 8080 \
    --trust-remote-code \
    --max-model-len 8192 \
    --gpu-memory-utilization 0.7 \
    --enforce-eager

