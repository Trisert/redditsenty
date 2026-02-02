#!/bin/bash
# Llama.cpp Server Launcher with GPU Support
# Automatically detects GPU and configures optimal settings

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Configuration
MODEL_PATH="${1:-$SCRIPT_DIR/models/Qwen3-4B-Instruct-2507-UD-Q8_K_XL.gguf}"
PORT="${2:-8080}"
CONTEXT_SIZE="${3:-4096}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Llama.cpp Server Launcher${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if model exists
if [ ! -f "$MODEL_PATH" ]; then
    echo -e "${RED}Error: Model not found at $MODEL_PATH${NC}"
    echo "Please run ./setup_model.sh first to download the model."
    exit 1
fi

echo -e "${GREEN}Model: $MODEL_PATH${NC}"
echo -e "${GREEN}Port: $PORT${NC}"
echo -e "${GREEN}Context Size: $CONTEXT_SIZE${NC}"
echo ""

# Detect GPU and set backend
GPU_BACKEND=""
GPU_LAYERS=0

# Check for NVIDIA GPU
if command -v nvidia-smi &> /dev/null; then
    echo -e "${GREEN}NVIDIA GPU detected!${NC}"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    GPU_BACKEND="cuda"
    GPU_LAYERS=999  # Offload all layers
    
# Check for AMD GPU (ROCm)
elif command -v rocminfo &> /dev/null; then
    echo -e "${GREEN}AMD GPU detected (ROCm)!${NC}"
    GPU_BACKEND="rocm"
    GPU_LAYERS=999
    
# Check for Apple Metal
elif [[ "$OSTYPE" == "darwin"* ]] && command -v system_profiler &> /dev/null; then
    if system_profiler SPDisplaysDataType | grep -q "Metal"; then
        echo -e "${GREEN}Apple Metal GPU detected!${NC}"
        GPU_BACKEND="metal"
        GPU_LAYERS=999
    fi
fi

if [ -z "$GPU_BACKEND" ]; then
    echo -e "${YELLOW}No GPU detected. Running on CPU only.${NC}"
    echo -e "${YELLOW}This will be slower but still functional.${NC}"
    GPU_LAYERS=0
else
    echo -e "${GREEN}GPU Backend: $GPU_BACKEND${NC}"
    echo -e "${GREEN}GPU Layers: $GPU_LAYERS (full offloading)${NC}"
fi

echo ""

# Check if llama-server is available
if ! command -v llama-server &> /dev/null; then
    echo -e "${YELLOW}llama-server not found in PATH${NC}"
    echo "Please install llama.cpp or provide the path to llama-server"
    echo ""
    echo "Installation options:"
    echo "  1. Build from source: https://github.com/ggerganov/llama.cpp"
    echo "  2. Use package manager (brew install llama.cpp on macOS)"
    echo ""
    
    # Check common locations
    COMMON_PATHS=(
        "$HOME/llama.cpp/build/bin/llama-server"
        "$HOME/llama.cpp/llama-server"
        "/usr/local/bin/llama-server"
        "/opt/llama.cpp/llama-server"
    )
    
    for path in "${COMMON_PATHS[@]}"; do
        if [ -f "$path" ]; then
            echo -e "${GREEN}Found llama-server at: $path${NC}"
            LLAMA_SERVER="$path"
            break
        fi
    done
    
    if [ -z "$LLAMA_SERVER" ]; then
        echo -e "${RED}llama-server not found. Please install llama.cpp first.${NC}"
        exit 1
    fi
else
    LLAMA_SERVER="llama-server"
fi

echo -e "${GREEN}Using: $LLAMA_SERVER${NC}"
echo ""

# Build command based on GPU backend
LAUNCH_CMD="$LLAMA_SERVER -m $MODEL_PATH --port $PORT -c $CONTEXT_SIZE"

if [ $GPU_LAYERS -gt 0 ]; then
    LAUNCH_CMD="$LAUNCH_CMD -ngl $GPU_LAYERS"
fi

# Add performance optimizations
LAUNCH_CMD="$LAUNCH_CMD -t $(nproc)"

echo -e "${BLUE}Launching server with command:${NC}"
echo -e "${YELLOW}$LAUNCH_CMD${NC}"
echo ""
echo -e "${GREEN}Server will be available at: http://localhost:$PORT${NC}"
echo -e "${GREEN}API documentation: http://localhost:$PORT/docs${NC}"
echo ""
echo -e "${BLUE}Press Ctrl+C to stop the server${NC}"
echo ""

# Launch the server
exec $LAUNCH_CMD
