# Reddit Sentiment Analysis with Local LLM

A complete sentiment analysis system that fetches Reddit posts, analyzes them using a local LLM (llama.cpp), and displays results in a modern web dashboard.

## Features

- **Real-time Reddit Data**: Fetches posts from any subreddit using Reddit's JSON API
- **Local LLM Inference**: Uses Qwen 3 4B model with llama.cpp for sentiment analysis
- **GPU Support**: Automatically detects and uses NVIDIA CUDA, AMD ROCm, or Apple Metal
- **Web Dashboard**: Modern, responsive UI with Chart.js visualizations
- **REST API**: FastAPI backend with endpoints for posts, sentiment distribution, and timelines
- **SQLite Storage**: Persistent storage of analyzed posts
- **Auto-refresh**: Dashboard updates every 5 minutes

## Architecture

```
┌─────────────┐      HTTP       ┌──────────────┐
│   Web UI    │ ◄──────────────► │  FastAPI     │
│  (Chart.js) │                  │   Backend    │
└─────────────┘                  └──────┬───────┘
                                        │
                                        │ SQLite
                                        ▼
                                ┌──────────────┐
                                │  Database    │
                                └──────────────┘
                                        ▲
                                        │ HTTP
                                        │
                               ┌────────┴────────┐
                               │  llama-server   │
                               │   (llama.cpp)   │
                               └────────┬────────┘
                                        │
                                        │ GGUF Model
                                        ▼
                               ┌─────────────────┐
                               │  Qwen 3 4B Q8   │
                               │  (Local LLM)    │
                               └─────────────────┘
```

## Quick Start

**Note: All commands should be run from the `redditsenty/` directory.**

```bash
cd /home/nicola/redditsenty
```

### 1. Install Dependencies

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync dependencies (creates virtual environment automatically)
uv sync

# Or install without syncing (if you prefer)
# uv pip install -e .
```

### 2. Download the Model

```bash
./setup_model.sh
```

This downloads the Qwen 3 4B model (Q8 quantization) from HuggingFace.

**Model Details:**
- **Model**: Qwen 3 4B (Q8_0 quantization)
- **Size**: ~4.5GB
- **VRAM**: 5-6GB for full GPU offloading
- **CPU RAM**: 6GB for CPU-only mode

### 3. Install llama.cpp

**Option A: Build from source**
```bash
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp

# For NVIDIA GPU:
cmake -B build -DGGML_CUDA=ON
cmake --build build --config Release

# For AMD GPU:
cmake -B build -DGGML_HIPBLAS=ON
cmake --build build --config Release

# For Apple Metal:
cmake -B build -DGGML_METAL=ON
cmake --build build --config Release

# For CPU only:
cmake -B build
cmake --build build --config Release

# Add to PATH
export PATH="$PWD/build/bin:$PATH"
```

**Option B: Package manager**
```bash
# macOS
brew install llama.cpp

# Ubuntu/Debian (if available)
apt install llama.cpp
```

### 4. Start the Services

You need to run two services simultaneously:

**Terminal 1 - Start llama.cpp server:**
```bash
./launch_server.sh
```

This will:
- Detect your GPU automatically
- Start llama-server on port 8080
- Load the Qwen 3 4B model

**Terminal 2 - Start FastAPI backend:**
```bash
uv run api.py
```

Or with explicit host/port:
```bash
uv run python api.py
```

### 5. Open the Dashboard

Open your browser and navigate to:
```
http://localhost:8000
```

## API Endpoints

### Get Posts
```
GET /api/posts?subreddit=LocalLLaMA&days=7&limit=25
```

Returns analyzed posts with sentiment data.

### Get Sentiment Distribution
```
GET /api/sentiment/distribution?subreddit=LocalLLaMA&days=7
```

Returns counts of positive, neutral, and negative posts.

### Get Sentiment Timeline
```
GET /api/sentiment/timeline?subreddit=LocalLLaMA&days=7
```

Returns daily sentiment counts for the specified time range.

### Trigger Analysis
```
POST /api/analyze?subreddit=LocalLLaMA&limit=25
```

Manually trigger fetching and analysis of new posts.

## Project Structure

```
.
├── api.py                 # FastAPI backend
├── reddit_fetcher.py      # Standalone Reddit fetcher (demo)
├── setup_model.sh         # Model download script
├── launch_server.sh       # llama.cpp server launcher
├── requirements.txt       # Python dependencies
├── models/                # Downloaded GGUF models
│   └── Qwen3-4B-Instruct-2507-UD-Q8_K_XL.gguf
├── web/                   # Frontend files
│   ├── index.html        # Main dashboard
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── app.js        # Dashboard logic
├── sentiment_analysis.db # SQLite database (created on first run)
└── README.md
```

## Configuration

### Environment Variables

```bash
# Model path (optional, defaults to ./models/Qwen3-4B-Instruct-2507-UD-Q8_K_XL.gguf)
export MODEL_PATH=/path/to/your/model.gguf

# llama-server URL (optional, defaults to http://localhost:8080)
export LLAMA_SERVER_URL=http://localhost:8080

# API port (optional, defaults to 8000)
export API_PORT=8000
```

### GPU Optimization

The `launch_server.sh` script automatically detects your GPU:

**NVIDIA (CUDA):**
- Requires NVIDIA GPU with Compute Capability 5.0+
- Installs with: `cmake -DGGML_CUDA=ON`

**AMD (ROCm):**
- Works with AMD Instinct and some consumer GPUs
- Installs with: `cmake -DGGML_HIPBLAS=ON`

**Apple (Metal):**
- Works on Apple Silicon (M1/M2/M3)
- Installs with: `cmake -DGGML_METAL=ON`

**CPU Only:**
- Works on any modern CPU
- Slower but no GPU required

### Manual GPU Layer Configuration

If you want to control GPU offloading manually:

```bash
# Full GPU offloading (fastest, requires 5-6GB VRAM)
llama-server -m models/Qwen3-4B-Instruct-2507-UD-Q8_K_XL.gguf --ngl 999

# Partial offloading (for limited VRAM)
llama-server -m models/Qwen3-4B-Instruct-2507-UD-Q8_K_XL.gguf --ngl 20

# CPU only
llama-server -m models/Qwen3-4B-Instruct-2507-UD-Q8_K_XL.gguf --ngl 0
```

## Troubleshooting

### "llama-server: command not found"

Make sure llama.cpp is built and in your PATH:
```bash
export PATH="/path/to/llama.cpp/build/bin:$PATH"
```

### "Failed to fetch Reddit data"

Reddit may rate-limit requests. Wait a few minutes and try again.

### Model download fails

Try alternative repositories in `setup_model.sh`:
- `hugging-quants/Qwen3-4B-GGUF`
- `bartowski/Qwen3-4B-GGUF`

### Out of memory

Use a smaller quantization:
- Q4_K_M (~2.5GB) instead of Q8_0 (~4.5GB)
- Reduce context size: `-c 2048` instead of `-c 4096`
- Use partial GPU offloading: `--ngl 20`

### Slow inference

- Enable GPU support (5-10x faster than CPU)
- Use batch processing (analyzes multiple posts at once)
- Reduce context size if you don't need long text analysis

## Performance Benchmarks

**Qwen 3 4B Q8 on RTX 3060 (12GB):**
- Inference speed: ~150-200 tokens/s
- Post analysis: ~2-3 seconds per post
- Batch processing: 10 posts in ~15 seconds

**Qwen 3 4B Q8 on CPU (i5-12500H):**
- Inference speed: ~20-30 tokens/s
- Post analysis: ~10-15 seconds per post
- Batch processing: 10 posts in ~2 minutes

## Customization

### Change the Model

Edit `setup_model.sh` to download a different model:
```bash
# Example: Use Llama 3.2 3B instead
REPO="hugging-quants/Llama-3.2-3B-Instruct-Q4_K_M-GGUF"
```

### Add More Subreddits

Edit `web/js/app.js` to add more subreddit options:
```javascript
const subreddits = [
    { value: "LocalLLaMA", label: "r/LocalLLaMA" },
    { value: "machinelearning", label: "r/machinelearning" },
    { value: "your_subreddit", label: "r/your_subreddit" }
];
```

### Custom Sentiment Prompt

Edit the prompt in `api.py`:
```python
prompt = f"""Your custom sentiment analysis prompt here...
Text: {text}
"""
```

## Development

### Run in Development Mode

```bash
# Start llama-server
./launch_server.sh

# Start API with auto-reload
uv run python -m uvicorn api:app --reload --port 8000
```

### Test API Endpoints

```bash
# Test posts endpoint
curl http://localhost:8000/api/posts?subreddit=LocalLLaMA&limit=5

# Test sentiment distribution
curl http://localhost:8000/api/sentiment/distribution

# Trigger manual analysis
curl -X POST http://localhost:8000/api/analyze?subreddit=LocalLLaMA
```

## License

This project is for educational purposes. Respect Reddit's API terms of service and rate limits.

## Credits

- [llama.cpp](https://github.com/ggerganov/llama.cpp) - Local LLM inference
- [Qwen 3](https://github.com/QwenLM/Qwen3) - Base model
- [Unsloth](https://github.com/unslothai/unsloth) - Model quantization
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [Chart.js](https://www.chart.js/) - Data visualization
