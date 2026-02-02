#!/bin/bash

# Setup script for Qwen 3 4B model
# Downloads using curl from HuggingFace direct link

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_DIR="$SCRIPT_DIR/models"

# Direct download URL
MODEL_URL="https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-UD-Q8_K_XL.gguf"

# Extract filename from URL
MODEL_FILE=$(basename "$MODEL_URL")
MODEL_PATH="$MODEL_DIR/$MODEL_FILE"

echo "========================================"
echo "Qwen 3 4B Model Setup Script"
echo "========================================"
echo ""

# Create models directory
echo "Creating models directory..."
mkdir -p "$MODEL_DIR"

# Check if model already exists
if [ -f "$MODEL_PATH" ]; then
    echo "Model already exists at $MODEL_PATH"
    echo "File size: $(ls -lh "$MODEL_PATH" | awk '{print $5}')"
    echo ""
    echo "To re-download, delete the existing file first:"
    echo "  rm $MODEL_PATH"
    echo ""
    echo "To run with llama-server:"
    echo "  ./launch_server.sh"
    exit 0
fi

# Download the model using curl
echo "Downloading Qwen 3 4B (UD-Q8_K_XL) from HuggingFace..."
echo "URL: $MODEL_URL"
echo "This may take several minutes (4.5GB file)..."
echo ""

if command -v curl &> /dev/null; then
    # Download with curl (shows default progress data)
    curl -L "$MODEL_URL" -o "$MODEL_PATH"
elif command -v wget &> /dev/null; then
    # Fallback to wget
    echo "Using wget..."
    wget "$MODEL_URL" -O "$MODEL_PATH"
else
    echo "ERROR: Neither curl nor wget found. Please install one of them."
    exit 1
fi

# Verify download
if [ -f "$MODEL_PATH" ]; then
    FILE_SIZE=$(ls -lh "$MODEL_PATH" | awk '{print $5}')
    echo ""
    echo "========================================"
    echo "Download Successful!"
    echo "========================================"
    echo "Model path: $MODEL_PATH"
    echo "File size: $FILE_SIZE"
    
    # Calculate MD5 if available
    if command -v md5sum &> /dev/null; then
        echo ""
        echo "MD5 checksum:"
        md5sum "$MODEL_PATH"
    elif command -v md5 &> /dev/null; then
        echo ""
        echo "MD5 checksum:"
        md5 "$MODEL_PATH"
    fi
    
    echo ""
    echo "========================================"
    echo "Next Steps:"
    echo "========================================"
    echo "1. Install llama.cpp (see README.md)"
    echo "2. Start the server: ./launch_server.sh"
    echo "3. Start the API: uv run python api.py"
    echo "4. Open browser: http://localhost:8000"
    echo ""
    echo "VRAM Requirements: ~5-6GB for full GPU offloading"
    echo "CPU RAM: ~6GB for CPU-only mode"
else
    echo ""
    echo "ERROR: Download failed!"
    echo "Please check your internet connection and try again."
    exit 1
fi
