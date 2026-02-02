# Reddit Sentiment Analysis - Development Guide

## Build / Test Commands

```bash
# Install dependencies
cd /home/nicola/redditsenty
uv sync

# Run API server (development with auto-reload)
uv run python -m uvicorn api:app --reload

# Run API server (production)
uv run python api.py

# Run tests
uv run pytest

# Run single test file
uv run pytest tests/test_api.py

# Run single test
uv run pytest tests/test_api.py::test_get_posts

# Lint with ruff
uv run ruff check .

# Format with black
uv run black .

# Format and check
uv run ruff check . --fix && uv run black .

# Type check (if mypy installed)
uv run mypy api.py
```

## Project Structure

```
redditsenty/
├── api.py                    # FastAPI backend (main entry point)
├── setup_model.sh            # Download Qwen 3 4B model
├── launch_server.sh          # Start llama.cpp server
├── pyproject.toml            # Project config & dependencies
├── README.md                 # User documentation
├── AGENTS.md                 # This file (for agents)
├── .gitignore
├── web/                      # Frontend
│   ├── index.html           # Dashboard HTML
│   ├── css/style.css        # Styles (Gruvbox dark theme)
│   └── js/app.js            # Frontend JS (Chart.js)
├── models/                   # GGUF models (gitignored)
│   └── Qwen3-4B-Instruct-2507-UD-Q8_K_XL.gguf
└── sentiment_analysis.db     # SQLite DB (gitignored)
```

## Code Style Guidelines

### Imports

- Group imports: stdlib → third-party → local
- Sort alphabetically within groups
- Use absolute imports

```python
# Correct
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query

# Avoid
from fastapi import FastAPI
import asyncio
from contextlib import asynccontextmanager
```

### Formatting

- Line length: 100 characters (configured in pyproject.toml)
- Use Black for formatting
- Use ruff for linting
- No trailing whitespace
- One blank line between function definitions

### Types

- Use Pydantic models for API schemas
- Use Optional[T] instead of Union[T, None]
- Use typing.List instead of list for compatibility

```python
# Pydantic models
class Post(BaseModel):
    id: str
    title: str
    author: str
    sentiment: Optional[str] = None
    analyzed_at: Optional[datetime] = None

# Function signatures
def get_posts(
    subreddit: Optional[str] = Query(None),
    days: int = Query(7),
    limit: int = Query(50),
) -> List[Post]:
```

### Naming Conventions

- **Variables/functions**: snake_case (`sentiment_score`, `get_posts`)
- **Classes**: PascalCase (`SentimentSummary`, `Post`)
- **Constants**: UPPER_SCASE (`AI_SUBREDDITS`, `DB_PATH`)
- **Private methods**: `_private_method(self)`
- **Private variables**: `_private_var`

### Error Handling

- Use FastAPI's HTTPException for API errors
- Log errors with print() (simple approach)
- Return meaningful error messages
- Use try/except for external calls (Reddit API, llama.cpp)

```python
try:
    async with session.post(url, json=payload) as response:
        if response.status == 200:
            result = await response.json()
except Exception as e:
    print(f"Error: {e}")
    raise HTTPException(status_code=500, detail="Service unavailable")
```

### Async/Await

- Use async for I/O-bound operations (HTTP requests, DB)
- Use asyncio.gather() for parallel operations
- Set timeouts on external requests

```python
async with aiohttp.ClientSession() as session:
    async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as response:
```

### Database (SQLite)

- Use parameterized queries (prevent SQL injection)
- Register datetime adapters for Python 3.12+
- Close connections properly
- Use context manager or try/finally

```python
conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
try:
    cursor.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
finally:
    conn.close()
```

### FastAPI Endpoints

- Use Query/Path/Body parameters appropriately
- Return Pydantic models for type safety
- Add docstrings to endpoints

```python
@app.get("/api/posts", response_model=List[Post])
async def get_posts(
    subreddit: Optional[str] = Query(None, description="Filter by subreddit"),
    limit: int = Query(50, ge=1, le=100),
):
    """Get posts with optional filtering by subreddit."""
```

### Frontend (JavaScript)

- Use ES6+ syntax (const/let, arrow functions, async/await)
- Modular functions with single responsibility
- Use EventSource for SSE streaming
- Escape user input with escapeHtml()

### Key Dependencies

- **FastAPI** Web framework
 -- **uvicorn** - ASGI server
- **aiohttp** - Async HTTP client
- **pydantic** - Data validation
- **sqlite3** - Database
- **Chart.js** - Frontend charts (via CDN)

### External Services

- **llama-server**: http://localhost:8080 (local LLM)
- **Reddit API**: https://www.reddit.com/r/{subreddit}/.json

### Development Workflow

1. Start llama-server: `./launch_server.sh` (tmux: `llama_srv`)
2. Start API: `uv run python api.py` (tmux: `reddit_api`)
3. Open http://localhost:8000
4. Make changes → auto-reload on API changes
5. Test with: `curl http://localhost:8000/api/stats`

### Testing

```bash
# Create test file
touch tests/test_api.py

# Test structure
def test_get_posts():
    response = client.get("/api/posts?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) <= 10
```

### Database Schema

```sql
CREATE TABLE posts (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    selftext TEXT,
    author TEXT,
    score INTEGER,
    ups INTEGER,
    downs INTEGER,
    num_comments INTEGER,
    created_utc DATETIME,
    permalink TEXT,
    url TEXT,
    subreddit TEXT,
    sentiment TEXT,
    sentiment_score REAL,
    analyzed_at DATETIME
);

CREATE VIRTUAL TABLE posts_fts USING fts5(title, selftext, content='posts', content_rowid='rowid');
```

### Adding New Endpoints

1. Define Pydantic model for response
2. Add endpoint with proper decorators
3. Document with docstring
4. Add to API router if splitting files
5. Update README.md with example

### Performance Notes

- Qwen 3 4B Q8 requires ~5GB VRAM or 6GB RAM
- GPU inference: ~150-200 tokens/s
- CPU inference: ~20-30 tokens/s
- Batch analyze posts in parallel for speed
