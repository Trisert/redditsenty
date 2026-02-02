#!/usr/bin/env python3
"""
Reddit Sentiment Analysis - FastAPI Backend
Collects posts from AI subreddits, analyzes sentiment, and enables topic search.
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
import json
import urllib.request
import urllib.parse
import aiohttp
import re
from datetime import datetime, date


def adapt_datetime(dt):
    return dt.isoformat()


def convert_datetime(val):
    return datetime.fromisoformat(val.decode() if isinstance(val, bytes) else val)


sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("DATETIME", convert_datetime)
sqlite3.register_adapter(date, lambda d: d.isoformat())
sqlite3.register_converter(
    "DATE", lambda val: date.fromisoformat(val.decode() if isinstance(val, bytes) else val)
)

# Top 15 AI-related subreddits
AI_SUBREDDITS = [
    "LocalLLaMA",
    "machinelearning",
    "artificial",
    "OpenAI",
    "ClaudeAI",
    "deeplearning",
    "MachineLearning",
    "ArtificialInteligence",
    "llama",
    "ollama",
    "transformers",
    "huggingface",
    "AIethics",
    "agetech",
    "LanguageModel",
]

FETCH_INTERVAL_MINUTES = 15
MAX_POSTS_PER_FETCH = 25
KEEP_MONTHS = 6

app = FastAPI(title="Reddit Sentiment Analysis API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
BASE_DIR = Path(__file__).parent
JS_DIR = BASE_DIR / "web" / "js"
CSS_DIR = BASE_DIR / "web" / "css"
JS_DIR.mkdir(parents=True, exist_ok=True)
CSS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/js", StaticFiles(directory=str(JS_DIR)), name="js")
app.mount("/css", StaticFiles(directory=str(CSS_DIR)), name="css")

DB_PATH = BASE_DIR / "sentiment_analysis.db"
LLAMA_SERVER_URL = "http://localhost:8080"


# Pydantic models
class Post(BaseModel):
    id: str
    title: str
    selftext: str
    author: str
    score: int
    ups: int
    downs: int
    num_comments: int
    created_utc: datetime
    permalink: str
    url: str
    subreddit: str
    sentiment: Optional[str] = None
    sentiment_score: Optional[float] = None
    analyzed_at: Optional[datetime] = None


class Citation(BaseModel):
    title: str
    subreddit: str
    author: str
    sentiment: str
    score: int
    url: str


class SentimentSummary(BaseModel):
    positive: int
    neutral: int
    negative: int
    total: int
    positive_percent: float
    negative_percent: float
    overall_tone: str  # "Mostly Positive", "Mostly Negative", "Mixed", "Neutral"


class SearchAnalysis(BaseModel):
    query: str
    summary: str  # AI-generated summary
    sentiment_summary: SentimentSummary
    positive_examples: List[Citation]
    negative_examples: List[Citation]
    neutral_examples: List[Citation]


class SentimentDistribution(BaseModel):
    positive: int
    neutral: int
    negative: int


class TimelineData(BaseModel):
    labels: List[str]
    positive: List[int]
    neutral: List[int]
    negative: List[int]


class SearchResult(BaseModel):
    query: str
    total_results: int
    positive: int
    neutral: int
    negative: int
    posts: List[Post]


class SubredditStats(BaseModel):
    subreddit: str
    total_posts: int
    positive: int
    neutral: int
    negative: int
    last_updated: Optional[str] = None


# Database functions
def init_db():
    """Initialize database with FTS5 support"""
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    # Main posts table
    cursor.execute("""
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
        )
    """)

    # FTS5 virtual table for full-text search
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5(
            title,
            selftext,
            content='posts',
            content_rowid='rowid'
        )
    """)

    # Triggers to keep FTS in sync
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS posts_ai AFTER INSERT ON posts BEGIN
            INSERT INTO posts_fts(rowid, title, selftext) 
            VALUES (new.rowid, new.title, new.selftext);
        END
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS posts_ad AFTER DELETE ON posts BEGIN
            INSERT INTO posts_fts(posts_fts, rowid, title, selftext) 
            VALUES('delete', old.rowid, old.title, old.selftext);
        END
    """)

    # Indexes
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_subreddit ON posts(subreddit)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_created ON posts(created_utc)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sentiment ON posts(sentiment)
    """)

    conn.commit()
    conn.close()


def cleanup_old_posts():
    """Remove posts older than KEEP_MONTHS"""
    cutoff = datetime.now() - timedelta(days=KEEP_MONTHS * 30)
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM posts WHERE created_utc < ?", (cutoff,))
    deleted = cursor.rowcount

    conn.commit()
    conn.close()

    if deleted > 0:
        print(f"Cleaned up {deleted} old posts")


def fetch_reddit_posts(subreddit: str, limit: int = 25) -> List[dict]:
    """Fetch posts from Reddit JSON API"""
    url = f"https://www.reddit.com/r/{subreddit}.json"
    headers = {"User-Agent": "SentimentAnalysisBot/1.0 (Educational Purpose)"}
    params = {"limit": limit}

    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(full_url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"Error fetching r/{subreddit}: {e}")
        return []

    posts = []
    for child in data["data"]["children"]:
        post_data = child["data"]
        posts.append(
            {
                "id": post_data["id"],
                "title": post_data["title"],
                "selftext": post_data.get("selftext", ""),
                "author": post_data["author"],
                "score": post_data["score"],
                "ups": post_data["ups"],
                "downs": post_data["downs"],
                "num_comments": post_data["num_comments"],
                "created_utc": datetime.fromtimestamp(post_data["created_utc"]),
                "permalink": f"https://reddit.com{post_data['permalink']}",
                "url": post_data.get("url", ""),
                "subreddit": post_data["subreddit"],
            }
        )

    return posts


async def analyze_sentiment(text: str) -> tuple:
    """Analyze sentiment using llama.cpp server"""
    prompt = f"""Analyze the sentiment of this Reddit post.
Classify as: POSITIVE, NEGATIVE, or NEUTRAL.
Score: -1.0 (negative) to +1.0 (positive).

Text: {text[:400]}

Respond exactly:
Sentiment: [POSITIVE/NEGATIVE/NEUTRAL]
Score: [number]"""

    payload = {
        "prompt": prompt,
        "temperature": 0.1,
        "max_tokens": 30,
        "stop": ["\n\n", "Response:"],
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{LLAMA_SERVER_URL}/completion",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status != 200:
                    return None, None

                result = await response.json()
                completion = result.get("content", "")

                # Parse response
                sentiment = "neutral"
                score = 0.0

                if "POSITIVE" in completion.upper():
                    sentiment = "positive"
                    score = 0.7
                elif "NEGATIVE" in completion.upper():
                    sentiment = "negative"
                    score = -0.7

                # Extract numeric score
                match = re.search(r"[-+]?\d*\.?\d+", completion)
                if match:
                    try:
                        s = float(match.group())
                        if -1.0 <= s <= 1.0:
                            score = s
                    except:
                        pass

                return sentiment, score

    except Exception as e:
        print(f"Sentiment analysis error: {e}")
        return None, None


def store_post(post: dict, sentiment: Optional[str] = None, score: Optional[float] = None):
    """Store post in database"""
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR REPLACE INTO posts 
        (id, title, selftext, author, score, ups, downs, num_comments, 
         created_utc, permalink, url, subreddit, sentiment, sentiment_score, analyzed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            post["id"],
            post["title"],
            post["selftext"],
            post["author"],
            post["score"],
            post["ups"],
            post["downs"],
            post["num_comments"],
            post["created_utc"],
            post["permalink"],
            post["url"],
            post["subreddit"],
            sentiment or None,
            score,
            datetime.now(),
        ),
    )

    conn.commit()
    conn.close()


async def fetch_and_analyze_subreddit(subreddit: str) -> int:
    """Fetch posts from a subreddit and analyze sentiment"""
    print(f"Fetching r/{subreddit}...")
    posts = fetch_reddit_posts(subreddit, MAX_POSTS_PER_FETCH)

    analyzed = 0
    for post in posts:
        # Skip if already exists
        conn = sqlite3.connect(
            DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM posts WHERE id = ?", (post["id"],))
        if cursor.fetchone():
            conn.close()
            continue
        conn.close()

        # Analyze sentiment
        text = f"{post['title']} {post['selftext'][:200]}"
        sentiment, score = await analyze_sentiment(text)

        store_post(post, sentiment, score)
        analyzed += 1

        # Rate limit
        await asyncio.sleep(0.5)

    print(f"  Analyzed {analyzed} new posts from r/{subreddit}")
    return analyzed


# Background fetcher
async def background_fetcher():
    """Continuously fetch posts from all AI subreddits"""
    while True:
        total_analyzed = 0
        for subreddit in AI_SUBREDDITS:
            try:
                analyzed = await fetch_and_analyze_subreddit(subreddit)
                total_analyzed += analyzed
            except Exception as e:
                print(f"Error fetching r/{subreddit}: {e}")

        # Cleanup old posts
        cleanup_old_posts()

        if total_analyzed > 0:
            print(f"Background fetch complete: {total_analyzed} new posts")

        # Wait 15 minutes
        await asyncio.sleep(FETCH_INTERVAL_MINUTES * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    # Startup
    init_db()
    print(f"Database initialized. Collecting from {len(AI_SUBREDDITS)} subreddits")
    print(f"Subreddits: {', '.join(AI_SUBREDDITS)}")

    # Start background fetcher
    fetcher_task = asyncio.create_task(background_fetcher())

    yield

    # Shutdown
    fetcher_task.cancel()
    try:
        await fetcher_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Reddit Sentiment Analysis API", lifespan=lifespan)

# Mount static files AFTER app creation
app.mount("/js", StaticFiles(directory=str(JS_DIR)), name="js")
app.mount("/css", StaticFiles(directory=str(CSS_DIR)), name="css")


# API Endpoints
@app.get("/")
async def root():
    """Serve the frontend"""
    web_path = BASE_DIR / "web" / "index.html"
    return FileResponse(str(web_path))


@app.get("/api/subreddits", response_model=List[str])
async def get_subreddits():
    """Get list of monitored subreddits"""
    return AI_SUBREDDITS


@app.get("/api/stats")
async def get_stats():
    """Get overall statistics"""
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    # Total posts
    cursor.execute("SELECT COUNT(*) FROM posts")
    total = cursor.fetchone()[0]

    # By sentiment
    cursor.execute("""
        SELECT sentiment, COUNT(*) FROM posts 
        WHERE sentiment IS NOT NULL GROUP BY sentiment
    """)
    sentiment_counts = dict(cursor.fetchall())

    # Posts per subreddit
    cursor.execute("""
        SELECT subreddit, COUNT(*) FROM posts 
        GROUP BY subreddit ORDER BY COUNT(*) DESC
    """)
    subreddit_counts = dict(cursor.fetchall())

    # Last updated
    cursor.execute("SELECT MAX(fetched_at) FROM posts")
    last_updated = cursor.fetchone()[0]

    conn.close()

    return {
        "total_posts": total,
        "sentiment": {
            "positive": sentiment_counts.get("positive", 0),
            "neutral": sentiment_counts.get("neutral", 0),
            "negative": sentiment_counts.get("negative", 0),
        },
        "subreddits": subreddit_counts,
        "last_updated": last_updated,
        "monitored_subreddits": len(AI_SUBREDDITS),
    }


@app.get("/api/search", response_model=SearchResult)
async def search_posts(
    q: str = Query(..., description="Search query"),
    subreddits: Optional[str] = Query(None, description="Comma-separated subreddits"),
    limit: int = Query(50, description="Max results"),
    sentiment: Optional[str] = Query(None, description="Filter by sentiment"),
):
    """Search posts using FTS5 full-text search"""
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    # FTS query to get matching rowids
    fts_query = "SELECT rowid FROM posts_fts WHERE posts_fts MATCH ?"
    cursor.execute(fts_query, [q])
    rowids = [r[0] for r in cursor.fetchall()]

    posts = []
    positive = neutral = negative = 0

    if rowids:
        # Fetch full posts from main table
        placeholders = ",".join("?" * len(rowids))
        cursor.execute(
            f"""
            SELECT id, title, selftext, author, score, ups, downs, num_comments,
                   created_utc, permalink, url, subreddit, sentiment, sentiment_score, analyzed_at
            FROM posts WHERE rowid IN ({placeholders})
        """,
            rowids,
        )

        all_posts = []
        for row in cursor.fetchall():
            post = Post(
                id=row[0],
                title=row[1],
                selftext=row[2],
                author=row[3],
                score=row[4],
                ups=row[5],
                downs=row[6],
                num_comments=row[7],
                created_utc=row[8],
                permalink=row[9],
                url=row[10],
                subreddit=row[11],
                sentiment=row[12],
                sentiment_score=row[13],
                analyzed_at=row[14],
            )
            all_posts.append(post)

        # Filter by subreddits if specified
        if subreddits:
            sub_list = [s.strip() for s in subreddits.split(",")]
            all_posts = [p for p in all_posts if p.subreddit in sub_list]

        # Filter by sentiment if specified
        if sentiment:
            all_posts = [p for p in all_posts if p.sentiment == sentiment]

        # Sort by score and limit
        all_posts.sort(key=lambda x: x.score or 0, reverse=True)
        all_posts = all_posts[:limit]

        # Count sentiments
        for post in all_posts:
            if post.sentiment == "positive":
                positive += 1
            elif post.sentiment == "negative":
                negative += 1
            else:
                neutral += 1

        posts = all_posts

    conn.close()

    return SearchResult(
        query=q,
        total_results=len(posts),
        positive=positive,
        neutral=neutral,
        negative=negative,
        posts=posts,
    )


@app.get("/api/search/analysis", response_model=SearchAnalysis)
async def search_analysis(
    q: str = Query(..., description="Search query"),
    subreddits: Optional[str] = Query(None, description="Comma-separated subreddits"),
    limit: int = Query(30, description="Max posts to analyze"),
):
    """Get detailed analysis of posts about a topic with AI summary"""
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    # FTS query
    fts_query = "SELECT rowid FROM posts_fts WHERE posts_fts MATCH ?"
    cursor.execute(fts_query, [q])
    rowids = [r[0] for r in cursor.fetchall()]

    if not rowids:
        conn.close()
        return SearchAnalysis(
            query=q,
            summary=f"No posts found about '{q}'",
            sentiment_summary=SentimentSummary(
                positive=0,
                neutral=0,
                negative=0,
                total=0,
                positive_percent=0,
                negative_percent=0,
                overall_tone="Unknown",
            ),
            positive_examples=[],
            negative_examples=[],
            neutral_examples=[],
        )

    # Fetch posts
    placeholders = ",".join("?" * len(rowids))
    cursor.execute(
        f"""
        SELECT id, title, selftext, author, score, ups, downs, num_comments,
               created_utc, permalink, url, subreddit, sentiment, sentiment_score, analyzed_at
        FROM posts WHERE rowid IN ({placeholders})
    """,
        rowids,
    )

    all_posts = []
    for row in cursor.fetchall():
        post = Post(
            id=row[0],
            title=row[1],
            selftext=row[2],
            author=row[3],
            score=row[4],
            ups=row[5],
            downs=row[6],
            num_comments=row[7],
            created_utc=row[8],
            permalink=row[9],
            url=row[10],
            subreddit=row[11],
            sentiment=row[12],
            sentiment_score=row[13],
            analyzed_at=row[14],
        )
        all_posts.append(post)

    # Filter by subreddits if specified
    if subreddits:
        sub_list = [s.strip() for s in subreddits.split(",")]
        all_posts = [p for p in all_posts if p.subreddit in sub_list]

    conn.close()

    # Sort by engagement
    all_posts.sort(key=lambda x: (x.score or 0) + (x.num_comments or 0), reverse=True)
    all_posts = all_posts[:limit]

    # Categorize by sentiment
    positive_posts = [p for p in all_posts if p.sentiment == "positive"]
    negative_posts = [p for p in all_posts if p.sentiment == "negative"]
    neutral_posts = [
        p for p in all_posts if p.sentiment != "positive" and p.sentiment != "negative"
    ]

    # Count sentiments
    positive_count = len(positive_posts)
    negative_count = len(negative_posts)
    neutral_count = len(neutral_posts)
    total = len(all_posts)

    positive_percent = (positive_count / total * 100) if total > 0 else 0
    negative_percent = (negative_count / total * 100) if total > 0 else 0

    # Determine overall tone
    if positive_percent > 60:
        overall_tone = "Mostly Positive"
    elif negative_percent > 60:
        overall_tone = "Mostly Negative"
    elif positive_percent > 40 and negative_percent > 40:
        overall_tone = "Mixed (Polarized)"
    elif positive_percent > 30 and negative_percent < 20:
        overall_tone = "Slightly Positive"
    elif negative_percent > 30 and positive_percent < 20:
        overall_tone = "Slightly Negative"
    else:
        overall_tone = "Neutral/Mixed"

    # Create citations
    def make_citation(post: Post) -> Citation:
        return Citation(
            title=post.title[:100] + "..." if len(post.title) > 100 else post.title,
            subreddit=post.subreddit,
            author=post.author,
            sentiment=post.sentiment or "unknown",
            score=post.score or 0,
            url=post.permalink,
        )

    positive_examples = [make_citation(p) for p in positive_posts[:3]]
    negative_examples = [make_citation(p) for p in negative_posts[:3]]
    neutral_examples = [make_citation(p) for p in neutral_posts[:3]]

    # Generate AI summary
    summary_text = await generate_topic_summary(
        q, all_posts, positive_count, negative_count, neutral_count, overall_tone
    )

    return SearchAnalysis(
        query=q,
        summary=summary_text,
        sentiment_summary=SentimentSummary(
            positive=positive_count,
            neutral=neutral_count,
            negative=negative_count,
            total=total,
            positive_percent=round(positive_percent, 1),
            negative_percent=round(negative_percent, 1),
            overall_tone=overall_tone,
        ),
        positive_examples=positive_examples,
        negative_examples=negative_examples,
        neutral_examples=neutral_examples,
    )


@app.get("/api/search/analysis/stream")
async def search_analysis_stream(
    q: str = Query(..., description="Search query"),
    subreddits: Optional[str] = Query(None, description="Comma-separated subreddits"),
    limit: int = Query(30, description="Max posts to analyze"),
):
    """Stream detailed analysis of posts about a topic with real-time progress"""

    async def event_generator():
        conn = sqlite3.connect(
            DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        cursor = conn.cursor()

        yield f"event: status\ndata: {json.dumps({'message': f'Searching for posts about "{q}"...'})}\n\n"

        # FTS query
        fts_query = "SELECT rowid FROM posts_fts WHERE posts_fts MATCH ?"
        cursor.execute(fts_query, [q])
        rowids = [r[0] for r in cursor.fetchall()]

        if not rowids:
            conn.close()
            yield f"event: complete\ndata: {
                json.dumps(
                    {
                        'query': q,
                        'summary': f"No posts found about '{q}'",
                        'sentiment_summary': {
                            'positive': 0,
                            'neutral': 0,
                            'negative': 0,
                            'total': 0,
                            'positive_percent': 0,
                            'negative_percent': 0,
                            'overall_tone': 'Unknown',
                        },
                        'positive_examples': [],
                        'negative_examples': [],
                        'neutral_examples': [],
                    }
                )
            }\n\n"
            return

        yield f"event: status\ndata: {json.dumps({'message': f'Found {len(rowids)} posts, fetching details...'})}\n\n"

        # Fetch posts
        placeholders = ",".join("?" * len(rowids))
        cursor.execute(
            f"""
            SELECT id, title, selftext, author, score, ups, downs, num_comments,
                   created_utc, permalink, url, subreddit, sentiment, sentiment_score, analyzed_at
            FROM posts WHERE rowid IN ({placeholders})
        """,
            rowids,
        )

        all_posts = []
        for row in cursor.fetchall():
            post = Post(
                id=row[0],
                title=row[1],
                selftext=row[2],
                author=row[3],
                score=row[4],
                ups=row[5],
                downs=row[6],
                num_comments=row[7],
                created_utc=row[8],
                permalink=row[9],
                url=row[10],
                subreddit=row[11],
                sentiment=row[12],
                sentiment_score=row[13],
                analyzed_at=row[14],
            )
            all_posts.append(post)

        conn.close()

        # Filter by subreddits if specified
        if subreddits:
            sub_list = [s.strip() for s in subreddits.split(",")]
            all_posts = [p for p in all_posts if p.subreddit in sub_list]

        # Sort by engagement
        all_posts.sort(key=lambda x: (x.score or 0) + (x.num_comments or 0), reverse=True)
        all_posts = all_posts[:limit]

        # Categorize by sentiment
        positive_posts = [p for p in all_posts if p.sentiment == "positive"]
        negative_posts = [p for p in all_posts if p.sentiment == "negative"]
        neutral_posts = [p for p in all_posts if p.sentiment not in ["positive", "negative"]]

        positive_count = len(positive_posts)
        negative_count = len(negative_posts)
        neutral_count = len(neutral_posts)
        total = len(all_posts)

        positive_percent = (positive_count / total * 100) if total > 0 else 0
        negative_percent = (negative_count / total * 100) if total > 0 else 0

        if positive_percent > 60:
            overall_tone = "Mostly Positive"
        elif negative_percent > 60:
            overall_tone = "Mostly Negative"
        elif positive_percent > 40 and negative_percent > 40:
            overall_tone = "Mixed (Polarized)"
        elif positive_percent > 30 and negative_percent < 20:
            overall_tone = "Slightly Positive"
        elif negative_percent > 30 and positive_percent < 20:
            overall_tone = "Slightly Negative"
        else:
            overall_tone = "Neutral/Mixed"

        # Create citations
        def make_citation(post: Post) -> dict:
            return {
                "title": post.title[:100] + "..." if len(post.title) > 100 else post.title,
                "subreddit": post.subreddit,
                "author": post.author,
                "sentiment": post.sentiment or "unknown",
                "score": post.score or 0,
                "url": post.permalink,
            }

        positive_examples = [make_citation(p) for p in positive_posts[:3]]
        negative_examples = [make_citation(p) for p in negative_posts[:3]]
        neutral_examples = [make_citation(p) for p in neutral_posts[:3]]

        # Send sentiment stats immediately
        yield f"event: sentiment\ndata: {
            json.dumps(
                {
                    'positive': positive_count,
                    'neutral': neutral_count,
                    'negative': negative_count,
                    'total': total,
                    'positive_percent': round(positive_percent, 1),
                    'negative_percent': round(negative_percent, 1),
                    'overall_tone': overall_tone,
                }
            )
        }\n\n"

        # Generate AI summary with streaming
        yield f"event: status\ndata: {json.dumps({'message': 'Generating AI summary...'})}\n\n"

        # Get content snippets
        snippets = []
        for post in all_posts[:10]:
            content = (
                f"Title: {post.title}\nContent: {post.selftext[:200] if post.selftext else 'N/A'}"
            )
            snippets.append(content)
        content_text = "\n---\n".join(snippets)

        prompt = f"""Analyze Reddit discussions about "{q}".

Stats: {positive_count} positive, {negative_count} negative, {neutral_count} neutral posts. Overall tone: {overall_tone}.

Recent posts:
{content_text}

Write a 2-3 sentence summary of what people are discussing and their general sentiment. Be concise and factual."""

        try:
            payload = {
                "prompt": f"<|im_start|>user\n{prompt}\n<|im_end|>\n<|im_start|>assistant\n",
                "temperature": 0.3,
                "max_tokens": 150,
                "stop": ["<|im_end|>"],
                "stream": True,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{LLAMA_SERVER_URL}/completion",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 200:
                        accumulated = ""
                        async for line in response.content:
                            line = line.decode("utf-8").strip()
                            if line.startswith("data: "):
                                try:
                                    data = json.loads(line[6:])
                                    if "content" in data:
                                        chunk = data["content"]
                                        accumulated += chunk
                                        yield f"event: summary_chunk\ndata: {json.dumps({'chunk': chunk, 'accumulated': accumulated})}\n\n"
                                except json.JSONDecodeError:
                                    pass
        except Exception as e:
            print(f"Error streaming summary: {e}")
            accumulated = f"Found {len(all_posts)} discussions about '{q}'. The community sentiment is {overall_tone.lower()} with {positive_count} positive, {negative_count} negative, and {neutral_count} neutral reactions."

        # Ensure accumulated is defined
        if "accumulated" not in dir():
            accumulated = f"Found {len(all_posts)} discussions about '{q}'. The community sentiment is {overall_tone.lower()} with {positive_count} positive, {negative_count} negative, and {neutral_count} neutral reactions."

        # Send final complete event
        yield f"event: complete\ndata: {
            json.dumps(
                {
                    'query': q,
                    'summary': accumulated
                    if 'accumulated' in dir()
                    else f"Found {len(all_posts)} discussions about '{q}'.",
                    'sentiment_summary': {
                        'positive': positive_count,
                        'neutral': neutral_count,
                        'negative': negative_count,
                        'total': total,
                        'positive_percent': round(positive_percent, 1),
                        'negative_percent': round(negative_percent, 1),
                        'overall_tone': overall_tone,
                    },
                    'positive_examples': positive_examples,
                    'negative_examples': negative_examples,
                    'neutral_examples': neutral_examples,
                }
            )
        }\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


async def generate_topic_summary(
    query: str, posts: List[Post], positive: int, negative: int, neutral: int, tone: str
) -> str:
    """Generate an AI summary of what people are saying about a topic"""

    if not posts:
        return f"No discussions found about '{query}'."

    # Get content snippets from top posts
    snippets = []
    for post in posts[:10]:
        content = f"Title: {post.title}\nContent: {post.selftext[:200] if post.selftext else 'N/A'}"
        snippets.append(content)

    content_text = "\n---\n".join(snippets)

    prompt = f"""Analyze Reddit discussions about "{query}".

Stats: {positive_count} positive, {negative_count} negative, {neutral_count} neutral posts. Overall tone: {overall_tone}.

Recent posts:
{content_text}

Write a 2-3 sentence summary of what people are discussing and their general sentiment. Be concise and factual."""

    try:
        payload = {
            "prompt": f"<|im_start|>user\n{prompt}\n<|im_end|>\n<|im_start|>assistant\n",
            "temperature": 0.3,
            "max_tokens": 150,
            "stop": ["<|im_end|>"],
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{LLAMA_SERVER_URL}/completion",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    content = result.get("content", "").strip()
                    # Clean up the response
                    content = content.replace("<|im_start|>", "").replace("<|im_end|>", "").strip()
                    if content:
                        return content

    except Exception as e:
        print(f"Error generating summary: {e}")

    # Fallback summary
    return f"Found {len(posts)} discussions about '{query}'. The community sentiment is {tone.lower()} with {positive} positive, {negative} negative, and {neutral} neutral reactions. People seem to be discussing {query} with varied opinions."


@app.get("/api/posts", response_model=List[Post])
async def get_posts(
    subreddit: Optional[str] = Query(None),
    days: int = Query(7),
    limit: int = Query(50),
    sentiment: Optional[str] = None,
):
    """Get posts with optional filtering"""
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    cutoff = datetime.now() - timedelta(days=days)

    # If subreddit is specified (not "all"), filter by it
    if subreddit and subreddit.lower() != "all":
        query = "SELECT * FROM posts WHERE subreddit = ? AND created_utc > ?"
        params: list[Any] = [subreddit, cutoff]
    else:
        # Return posts from all subreddits
        query = "SELECT * FROM posts WHERE created_utc > ?"
        params = [cutoff]

    if sentiment:
        query += " AND sentiment = ?"
        params.append(sentiment)

    query += " ORDER BY created_utc DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)

    posts = []
    for row in cursor.fetchall():
        posts.append(
            Post(
                id=row[0],
                title=row[1],
                selftext=row[2],
                author=row[3],
                score=row[4],
                ups=row[5],
                downs=row[6],
                num_comments=row[7],
                created_utc=row[8],
                permalink=row[9],
                url=row[10],
                subreddit=row[11],
                sentiment=row[12],
                sentiment_score=row[13],
                analyzed_at=row[14],
            )
        )

    conn.close()
    return posts


@app.get("/api/sentiment/distribution", response_model=SentimentDistribution)
async def get_distribution(
    subreddit: Optional[str] = Query(None),
    days: int = Query(7),
):
    """Get sentiment distribution"""
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    cutoff = datetime.now() - timedelta(days=days)

    if subreddit and subreddit.lower() != "all":
        cursor.execute(
            """
            SELECT sentiment, COUNT(*) FROM posts 
            WHERE subreddit = ? AND created_utc > ? AND sentiment IS NOT NULL
            GROUP BY sentiment
        """,
            (subreddit, cutoff),
        )
    else:
        cursor.execute(
            """
            SELECT sentiment, COUNT(*) FROM posts 
            WHERE created_utc > ? AND sentiment IS NOT NULL
            GROUP BY sentiment
        """,
            (cutoff,),
        )

    distribution = {"positive": 0, "neutral": 0, "negative": 0}
    for sentiment, count in cursor.fetchall():
        if sentiment and sentiment.lower() in distribution:
            distribution[sentiment.lower()] = count

    conn.close()
    return SentimentDistribution(**distribution)


@app.get("/api/sentiment/timeline", response_model=TimelineData)
async def get_timeline(
    subreddit: Optional[str] = Query(None),
    days: int = Query(7),
):
    """Get sentiment over time"""
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cursor = conn.cursor()

    cutoff = datetime.now() - timedelta(days=days)

    if subreddit and subreddit.lower() != "all":
        cursor.execute(
            """
            SELECT DATE(created_utc) as date, sentiment, COUNT(*)
            FROM posts 
            WHERE subreddit = ? AND created_utc > ? AND sentiment IS NOT NULL
            GROUP BY DATE(created_utc), sentiment
            ORDER BY date DESC
        """,
            (subreddit, cutoff),
        )
    else:
        cursor.execute(
            """
            SELECT DATE(created_utc) as date, sentiment, COUNT(*)
            FROM posts 
            WHERE created_utc > ? AND sentiment IS NOT NULL
            GROUP BY DATE(created_utc), sentiment
            ORDER BY date DESC
        """,
            (cutoff,),
        )

    date_data = {}
    for date, sentiment, count in cursor.fetchall():
        if date not in date_data:
            date_data[date] = {"positive": 0, "neutral": 0, "negative": 0}
        if sentiment and sentiment.lower() in date_data[date]:
            date_data[date][sentiment.lower()] = count

    conn.close()

    labels = []
    positive = []
    neutral = []
    negative = []

    for i in range(days - 1, -1, -1):
        date = (cutoff + timedelta(days=i)).strftime("%Y-%m-%d")
        labels.append(date)
        data = date_data.get(date, {"positive": 0, "neutral": 0, "negative": 0})
        positive.append(data["positive"])
        neutral.append(data["neutral"])
        negative.append(data["negative"])

    return TimelineData(labels=labels, positive=positive, neutral=neutral, negative=negative)


@app.post("/api/analyze")
async def trigger_analysis(subreddit: str = "LocalLLaMA", limit: int = 25):
    """Manually trigger analysis for a subreddit"""
    analyzed = await fetch_and_analyze_subreddit(subreddit)
    return {"message": f"Analyzed {analyzed} posts", "subreddit": subreddit}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
