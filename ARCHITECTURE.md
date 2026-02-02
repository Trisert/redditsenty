# Reddit Sentiment Analysis System - Architecture Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [High-Level Architecture](#high-level-architecture)
3. [Component Architecture](#component-architecture)
4. [Database Schema](#database-schema)
5. [API Reference](#api-reference)
6. [Frontend Architecture](#frontend-architecture)
7. [Data Flow](#data-flow)
8. [Deployment](#deployment)

---

## System Overview

The **Reddit Sentiment Analysis System** is a full-stack application that:
- Monitors 15 AI-related subreddits for new posts
- Analyzes sentiment using a local LLM (Qwen 3 4B via llama.cpp)
- Stores data in SQLite with full-text search (FTS5)
- Provides a web dashboard with real-time visualizations
- Offers AI-powered topic analysis with streaming responses

### Key Technologies

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI (Python 3.10+) |
| **Database** | SQLite with FTS5 |
| **LLM Inference** | llama.cpp |
| **Model** | Qwen 3 4B Instruct (Q8 quantized, ~4.5GB) |
| **Frontend** | Vanilla JavaScript + Chart.js |
| **Communication** | REST API + Server-Sent Events (SSE) |

---

## High-Level Architecture

```mermaid
graph TB
    subgraph "External Services"
        REDDIT[Reddit JSON API]
        HF[HuggingFace Models]
    end

    subgraph "Reddit Sentiment Analysis System"
        subgraph "Frontend Layer"
            WEB[Web Dashboard<br/>web/index.html]
            JS[JavaScript App<br/>web/js/app.js]
            CHARTS[Chart.js<br/>Visualizations]
        end

        subgraph "Backend Layer"
            API[FastAPI Server<br/>api.py]
            BG[Background Fetcher<br/>15-min interval]
            ENDPOINTS[REST API Endpoints]
        end

        subgraph "AI/ML Layer"
            LLAMA[llama.cpp Server<br/>localhost:8080]
            MODEL[Qwen 3 4B Q8<br/>Local LLM]
        end

        subgraph "Data Layer"
            DB[(SQLite Database<br/>sentiment_analysis.db)]
            FTS[(FTS5 Virtual Table<br/>Full-Text Search)]
        end
    end

    WEB <--> API
    JS --> CHARTS
    JS --> API
    API --> ENDPOINTS
    BG --> API
    API --> DB
    API --> FTS
    API --> LLAMA
    LLAMA --> MODEL
    BG --> REDDIT
    MODEL -.-> HF

    style WEB fill:#458588,stroke:#282828,color:#ebdbb2
    style API fill:#d79921,stroke:#282828,color:#ebdbb2
    style LLAMA fill:#b16286,stroke:#282828,color:#ebdbb2
    style DB fill:#689d6a,stroke:#282828,color:#ebdbb2
    style REDDIT fill:#cc241d,stroke:#282828,color:#ebdbb2
```

---

## Component Architecture

### 1. Backend Components

```mermaid
graph TB
    subgraph "FastAPI Application (api.py)"
        STARTUP([Lifespan Manager])

        subgraph "Data Collection"
            FETCH[fetch_reddit_posts<br/>Reddit JSON API Client]
            ANALYZE[analyze_sentiment<br/>LLM-based Classification]
            STORE[store_post<br/>Database Persistence]
        end

        subgraph "Background Tasks"
            BG_FETCHER[background_fetcher<br/>15-min Loop]
            CLEANUP[cleanup_old_posts<br/>6-month Retention]
        end

        subgraph "API Endpoints"
            GET_POSTS[/api/posts<br/>Get Filtered Posts]
            SEARCH[/api/search<br/>FTS5 Search]
            SEARCH_ANAL[/api/search/analysis<br/>AI Topic Analysis]
            STREAM[/api/search/analysis/stream<br/>SSE Streaming]
            DIST[/api/sentiment/distribution<br/>Stats by Period]
            TIME[/api/sentiment/timeline<br/>Time Series Data]
            STATS[/api/stats<br/>Overall Statistics]
        end

        subgraph "Database Layer"
            INIT[init_db<br/>Schema Setup]
            FTS_SYNC[FTS5 Triggers<br/>Auto-sync]
        end
    end

    STARTUP --> INIT
    INIT --> FTS_SYNC
    STARTUP --> BG_FETCHER
    BG_FETCHER --> FETCH
    BG_FETCHER --> CLEANUP
    FETCH --> ANALYZE
    ANALYZE --> STORE

    GET_POSTS --> DB_QUERY[(Database Query)]
    SEARCH --> DB_QUERY
    SEARCH_ANAL --> DB_QUERY
    SEARCH_ANAL --> LLAMA_CALL[(LLM Inference)]
    STREAM --> DB_QUERY
    STREAM --> LLAMA_CALL
    DIST --> DB_QUERY
    TIME --> DB_QUERY
    STATS --> DB_QUERY

    style STARTUP fill:#d79921,stroke:#282828,color:#ebdbb2
    style BG_FETCHER fill:#458588,stroke:#282828,color:#ebdbb2
    style SEARCH_ANAL fill:#b16286,stroke:#282828,color:#ebdbb2
    style STREAM fill:#b16286,stroke:#282828,color:#ebdbb2
```

### 2. Frontend Components

```mermaid
graph TB
    subgraph "Web Dashboard (web/)"
        HTML[index.html<br/>Single Page App]

        subgraph "JavaScript Modules (app.js)"
            INIT[Initialization<br/>DOMContentLoaded]
            CHART[Chart Manager<br/>Chart.js Wrapper]
            API[API Client<br/>fetch/fetch SSE]
            UI[UI Manager<br/>DOM Updates]
            SEARCH[Search Handler<br/>Form Processing]
        end

        subgraph "Visualizations"
            DOUGHNUT[Doughnut Chart<br/>Sentiment Distribution]
            LINE[Line Chart<br/>Timeline Trends]
        end

        subgraph "UI Components"
            POSTS_TBL[Posts Table<br/>Sortable Results]
            ANALYSIS[Analysis Section<br/>AI Summary Display]
            CITATIONS[Citations Grid<br/>Example Posts]
            SEARCH_INFO[Search Info<br/>Stats Bar]
        end
    end

    INIT --> CHART
    INIT --> API
    INIT --> UI
    SEARCH --> API
    API --> CHART
    API --> UI
    CHART --> DOUGHNUT
    CHART --> LINE
    UI --> POSTS_TBL
    UI --> ANALYSIS
    UI --> CITATIONS
    UI --> SEARCH_INFO

    style HTML fill:#458588,stroke:#282828,color:#ebdbb2
    style DOUGHNUT fill:#98971a,stroke:#282828,color:#ebdbb2
    style LINE fill:#d65d0e,stroke:#282828,color:#ebdbb2
```

---

## Database Schema

### Tables and Relationships

```mermaid
erDiagram
    posts ||--o{ posts_fts : "FTS index"
    posts {
        string id PK "Reddit post ID"
        text title "Post title"
        text selftext "Post body content"
        string author "Reddit username"
        integer score "Net upvotes"
        integer ups "Upvotes"
        integer downs "Downvotes"
        integer num_comments "Comment count"
        timestamp created_utc "Post timestamp"
        text permalink "Reddit URL"
        text url "External link"
        string subreddit "Subreddit name"
        string sentiment "positive/negative/neutral"
        real sentiment_score "-1.0 to +1.0"
        timestamp analyzed_at "Analysis time"
        timestamp fetched_at "Fetch time"
    }

    posts_fts {
        rowid rowid PK "Row ID"
        text title "FTS indexed title"
        text selftext "FTS indexed content"
    }
```

### Indexes and Triggers

```mermaid
graph TB
    subgraph "SQLite Database"
        subgraph "Tables"
            POSTS[posts<br/>Main data]
            FTS[posts_fts<br/>FTS5 virtual table]
        end

        subgraph "Indexes"
            IDX1[idx_subreddit<br/>ON posts(subreddit)]
            IDX2[idx_created<br/>ON posts(created_utc)]
            IDX3[idx_sentiment<br/>ON posts(sentiment)]
        end

        subgraph "Triggers"
            TRG1[posts_ai<br/>AFTER INSERT]
            TRG2[posts_ad<br/>AFTER DELETE]
        end
    end

    POSTS --> IDX1
    POSTS --> IDX2
    POSTS --> IDX3
    TRG1 --> FTS
    TRG2 --> FTS
    POSTS -.->|sync| FTS

    style POSTS fill:#689d6a,stroke:#282828,color:#ebdbb2
    style FTS fill:#458588,stroke:#282828,color:#ebdbb2
```

**Schema SQL:**
```sql
-- Main posts table (api.py:156-175)
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    title TEXT,
    selftext TEXT,
    author TEXT,
    score INTEGER,
    ups INTEGER,
    downs INTEGER,
    num_comments INTEGER,
    created_utc TIMESTAMP,
    permalink TEXT,
    url TEXT,
    subreddit TEXT,
    sentiment TEXT,
    sentiment_score REAL,
    analyzed_at TIMESTAMP,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- FTS5 virtual table (api.py:178-185)
CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5(
    title,
    selftext,
    content='posts',
    content_rowid='rowid'
);

-- Triggers (api.py:188-200)
CREATE TRIGGER IF NOT EXISTS posts_ai AFTER INSERT ON posts BEGIN
    INSERT INTO posts_fts(rowid, title, selftext)
    VALUES (new.rowid, new.title, new.selftext);
END;

CREATE TRIGGER IF NOT EXISTS posts_ad AFTER DELETE ON posts BEGIN
    INSERT INTO posts_fts(posts_fts, rowid, title, selftext)
    VALUES('delete', old.rowid, old.title, old.selftext);
END;
```

---

## API Reference

### Endpoint Overview

```mermaid
graph LR
    subgraph "REST API Endpoints"
        GET1[GET /<br/>Serve Dashboard]
        GET2[GET /api/subreddits<br/>List Subreddits]
        GET3[GET /api/posts<br/>Fetch Posts]
        GET4[GET /api/search<br/>Search Posts]
        GET5[GET /api/search/analysis<br/>Topic Analysis]
        GET6[GET /api/search/analysis/stream<br/>Stream Analysis]
        GET7[GET /api/sentiment/distribution<br/>Distribution Stats]
        GET8[GET /api/sentiment/timeline<br/>Timeline Data]
        GET9[GET /api/stats<br/>Overall Stats]
        POST1[POST /api/analyze<br/>Trigger Analysis]
    end

    style GET6 fill:#b16286,stroke:#282828,color:#ebdbb2
    style GET5 fill:#b16286,stroke:#282828,color:#ebdbb2
```

### Detailed Endpoint Specifications

| Endpoint | Method | Params | Returns | Location |
|----------|--------|--------|---------|----------|
| `/` | GET | - | HTML page | api.py:448 |
| `/api/subreddits` | GET | - | `List[str]` | api.py:455 |
| `/api/posts` | GET | `subreddit`, `days`, `limit`, `sentiment` | `List[Post]` | api.py:1019 |
| `/api/search` | GET | `q`, `subreddits`, `limit`, `sentiment` | `SearchResult` | api.py:504 |
| `/api/search/analysis` | GET | `q`, `subreddits`, `limit` | `SearchAnalysis` | api.py:592 |
| `/api/search/analysis/stream` | GET | `q`, `subreddits`, `limit` | SSE Stream | api.py:737 |
| `/api/sentiment/distribution` | GET | `subreddit`, `days` | `SentimentDistribution` | api.py:1076 |
| `/api/sentiment/timeline` | GET | `subreddit`, `days` | `TimelineData` | api.py:1115 |
| `/api/stats` | GET | - | `Stats` | api.py:461 |
| `/api/analyze` | POST | `subreddit`, `limit` | `{message}` | api.py:1174 |

### Pydantic Data Models

```mermaid
classDiagram
    class Post {
        +str id
        +str title
        +str selftext
        +str author
        +int score
        +datetime created_utc
        +str permalink
        +str subreddit
        +Optional[str] sentiment
        +Optional[float] sentiment_score
        +Optional[datetime] analyzed_at
    }

    class Citation {
        +str title
        +str subreddit
        +str author
        +str sentiment
        +int score
        +str url
    }

    class SentimentSummary {
        +int positive
        +int neutral
        +int negative
        +int total
        +float positive_percent
        +float negative_percent
        +str overall_tone
    }

    class SearchAnalysis {
        +str query
        +str summary
        +SentimentSummary sentiment_summary
        +List[Citation] positive_examples
        +List[Citation] negative_examples
        +List[Citation] neutral_examples
    }

    class SearchResult {
        +str query
        +int total_results
        +int positive
        +int neutral
        +int negative
        +List[Post] posts
    }

    class TimelineData {
        +List[str] labels
        +List[int] positive
        +List[int] neutral
        +List[int] negative
    }

    SearchAnalysis --> SentimentSummary
    SearchAnalysis --> Citation
    SearchResult --> Post
```

---

## Frontend Architecture

### Application State

```mermaid
stateDiagram-v2
    [*] --> Browse

    Browse --> Searching: Submit search form
    Searching --> Browse: Click subreddit tab

    Browse --> Loading: Refresh/data load
    Searching --> Streaming: Start search
    Streaming --> Browse: Complete/Error

    Loading --> Browse: Data loaded
    Loading --> Error: API error
    Error --> Browse: Dismiss

    note right of Browse
        Normal mode:
        - View all posts
        - Filter by subreddit
        - Set date range
    end note

    note right of Searching
        Search mode:
        - Full-text query
        - Filter by subreddit
        - View sentiment stats
    end note

    note right of Streaming
        AI Analysis:
        - Real-time summary
        - Streaming tokens
        - Citations display
    end note
```

### SSE Event Flow

```mermaid
sequenceDiagram
    participant User
    participant JS as JavaScript (app.js)
    participant API as FastAPI
    participant DB as SQLite
    participant LLM as llama.cpp

    User->>JS: Submit search query
    JS->>API: GET /api/search/analysis/stream?q=...
    activate API

    API->>DB: FTS5 search for posts
    DB-->>API: rowid results
    API-->>JS: event: status (Searching...)

    API->>DB: Fetch full posts
    DB-->>API: Post data
    API-->>JS: event: status (Found N posts)

    API->>API: Calculate sentiment stats
    API-->>JS: event: sentiment (stats)

    JS->>JS: Update UI with stats
    JS->>JS: Update charts

    API->>LLM: Generate summary
    activate LLM
    loop Streaming tokens
        LLM-->>API: content chunks
        API-->>JS: event: summary_chunk
        JS->>JS: Update summary text
    end
    deactivate LLM

    API-->>JS: event: complete (final data)
    deactivate API

    JS->>JS: Display citations
    JS->>JS: Show posts table
```

---

## Data Flow

### 1. Background Fetching Flow

```mermaid
sequenceDiagram
    participant BG as Background Fetcher
    participant REDDIT as Reddit API
    participant DB as Database
    participant LLM as llama.cpp

    Note over BG: Every 15 minutes

    loop For each subreddit (15 total)
        BG->>REDDIT: GET /r/{subreddit}.json
        REDDIT-->>BG: Posts data (max 25)

        loop For each new post
            BG->>DB: Check if exists
            alt Post not in DB
                BG->>LLM: Analyze sentiment
                LLM-->>BG: sentiment + score
                BG->>DB: Store with sentiment
                Note over BG: 0.5s delay (rate limit)
            end
        end
    end

    BG->>DB: DELETE posts older than 6 months
    Note over BG: Wait 15 minutes
```

### 2. Sentiment Analysis Flow

```mermaid
flowchart TD
    START([Reddit Post Fetched])

    TEXT[Extract Text<br/>title + selftext[:400]]
    PROMPT[Create Prompt<br/>Classify + Score]

    LLAMACALL[Call llama.cpp<br/>/completion endpoint]

    PARSE[Parse Response<br/>Extract sentiment/score]

    DECISION{Valid Response?}

    SUCCESS[Store in DB<br/>with sentiment]
    FAIL[Mark as neutral<br/>score = 0.0]

    START --> TEXT
    TEXT --> PROMPT
    PROMPT --> LLAMACALL
    LLAMACALL --> PARSE
    PARSE --> DECISION
    DECISION -->|Yes| SUCCESS
    DECISION -->|No/Error| FAIL

    style LLAMACALL fill:#b16286,stroke:#282828,color:#ebdbb2
    style SUCCESS fill:#689d6a,stroke:#282828,color:#ebdbb2
    style FAIL fill:#cc241d,stroke:#282828,color:#ebdbb2
```

### 3. Search & Analysis Flow

```mermaid
flowchart TD
    QUERY([User Search Query])

    FTS[FTS5 Search<br/>posts_fts MATCH]
    ROWIDS[Get matching rowids]

    FETCH[Fetch full posts<br/>FROM posts WHERE rowid IN]

    FILTER{Filters Applied?}
    SUBFILTER[Filter by subreddit]
    SENTFILTER[Filter by sentiment]

    SORT[Sort by score<br/>DESC LIMIT 30]

    CATEGORIZE[Categorize by sentiment<br/>positive/negative/neutral]

    STATS[Calculate statistics<br/>counts, percentages, tone]

    STREAM[Start SSE Stream]

    SEND_STATS[Send sentiment event]
    LLM_SUM[Generate AI Summary<br/>Streaming response]
    SEND_COMPLETE[Send complete event<br/>with citations]

    QUERY --> FTS
    FTS --> ROWIDS
    ROWIDS --> FETCH
    FETCH --> FILTER
    FILTER -->|subreddit| SUBFILTER
    FILTER -->|sentiment| SENTFILTER
    SUBFILTER --> SORT
    SENTFILTER --> SORT
    SORT --> CATEGORIZE
    CATEGORIZE --> STATS
    STATS --> STREAM
    STREAM --> SEND_STATS
    SEND_STATS --> LLM_SUM
    LLM_SUM --> SEND_COMPLETE

    style FTS fill:#458588,stroke:#282828,color:#ebdbb2
    style LLM_SUM fill:#b16286,stroke:#282828,color:#ebdbb2
    style STREAM fill:#d79921,stroke:#282828,color:#ebdbb2
```

---

## Deployment

### System Startup Sequence

```mermaid
sequenceDiagram
    participant User
    participant Shell as Terminal
    participant Script as launch_server.sh
    participant LLAMA as llama.cpp
    participant API as uvicorn

    User->>Shell: ./launch_server.sh
    activate Script

    Script->>Script: Detect GPU (NVIDIA/AMD/Apple)
    Script->>Script: Set GPU layers & threads

    alt GPU detected
        Script->>LLAMA: ./llama-server<br/>--gpu-layers N<br/>-t $(nproc)
    else CPU only
        Script->>LLAMA: ./llama-server<br/>-t $(nproc)
    end

    activate LLAMA
    LLAMA-->>Script: Server listening on :8080
    deactivate LLAMA

    Note over Script,LLAMA: LLM server ready

    Script->>API: python api.py
    activate API

    API->>API: Initialize database
    API->>API: Create background task

    API->>API: Start background fetcher
    loop Every 15 min
        API->>API: Fetch & analyze posts
    end

    API-->>Script: Server listening on :8000
    deactivate API

    Script-->>User: ✓ System ready

    Note over User,API: Dashboard: http://localhost:8000
```

### Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **RAM** | 8GB | 16GB+ |
| **VRAM** | 0GB (CPU) | 5-6GB (GPU) |
| **Storage** | 6GB | 10GB+ |
| **CPU** | 4 cores | 8+ cores |
| **GPU** | - | NVIDIA RTX 3060+ |

### Configuration Files

**`.env` (optional):**
```bash
MODEL_PATH=./models/qwen2-7b-instruct-q8_0.gguf
LLAMA_SERVER_URL=http://localhost:8080
API_PORT=8000
```

**`pyproject.toml` key dependencies:**
```toml
[project]
name = "reddit-sentiment"
dependencies = [
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "aiohttp>=3.9.0",
    "pydantic>=2.5.0",
]
```

---

## Performance Characteristics

### Current System State
- **307 analyzed posts** from 13 subreddits
- **Sentiment distribution:**
  - Positive: 47 (15.3%)
  - Neutral: 187 (60.9%)
  - Negative: 73 (23.8%)
- **Most active subreddits:** LocalLLaMA (30), ArtificialInteligence (29), MachineLearning (28)

### Performance Metrics
| Operation | Time | Notes |
|-----------|------|-------|
| **Sentiment analysis** | ~2-3s/post | GPU-accelerated |
| **Full-text search** | <100ms | FTS5 indexed |
| **Timeline query** | <200ms | Aggregated |
| **Topic analysis** | 5-10s | With LLM streaming |
| **Background fetch** | ~5-10min | 15 subreddits × 25 posts |

### Scaling Considerations
- **Database**: SQLite suitable for <10M posts
- **Inference**: llama.cpp scales with GPU VRAM
- **Concurrency**: FastAPI async handles high load
- **Search**: FTS5 provides O(log n) lookups

---

## Development Notes

### Code Organization

```
redditsenty/
├── api.py                 # FastAPI backend (1185 lines)
│   ├── Database setup (lines 150-231)
│   ├── Reddit fetcher (lines 233-269)
│   ├── Sentiment analysis (lines 272-329)
│   ├── Background tasks (lines 397-437)
│   └── API endpoints (lines 448-1179)
│
├── web/
│   ├── index.html        # Dashboard UI
│   └── js/
│       └── app.js        # Frontend logic (485 lines)
│           ├── Chart initialization (lines 83-127)
│           ├── Data loading (lines 129-174)
│           ├── Search handling (lines 176-314)
│           └── UI updates (lines 393-484)
│
├── reddit_fetcher.py     # Standalone fetcher (96 lines)
├── setup_model.sh        # Model download script
└── launch_server.sh      # Server launcher (134 lines)
```

### Key Design Patterns

1. **Async/Await**: All I/O operations use asyncio
2. **Context Manager**: Lifespan management for startup/shutdown
3. **Streaming**: SSE for real-time AI responses
4. **FTS5**: Triggers keep search index in sync
5. **Rate Limiting**: 0.5s delay between LLM calls
6. **Caching**: Duplicate posts skipped by ID

### Extension Points

- **Add subreddits**: Modify `AI_SUBREDDITS` list (api.py:25)
- **Custom prompts**: Edit `analyze_sentiment` function (api.py:274)
- **New charts**: Add to `initCharts` in app.js (line 83)
- **Additional filters**: Extend query parameters
- **Export functionality**: Add CSV/JSON endpoints

---

## License & Credits

This is an educational project demonstrating:
- FastAPI backend architecture
- Local LLM integration with llama.cpp
- SQLite FTS5 full-text search
- Server-Sent Events (SSE) streaming
- Modern JavaScript dashboard
- Real-time data visualization

**Model**: Qwen 3 4B Instruct by Alibaba Cloud
**Framework**: llama.cpp by Georgi Gerganov
