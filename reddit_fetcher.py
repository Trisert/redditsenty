#!/usr/bin/env python3
"""
Reddit Sentiment Analysis - Data Fetcher
Fetches posts from r/LocalLLaMA using Reddit's JSON API
"""

import urllib.request
import json
from datetime import datetime
from urllib.parse import urlencode


def fetch_subreddit(subreddit, limit=25):
    """Fetch posts from a subreddit using the .json endpoint"""
    params = {"limit": limit}
    url = f"https://www.reddit.com/r/{subreddit}.json?{urlencode(params)}"
    headers = {"User-Agent": "SentimentAnalysisBot/1.0 (Educational Purpose)"}

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_posts(data):
    """Extract relevant fields from Reddit JSON response"""
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


def display_posts(posts):
    """Display fetched posts in a readable format"""
    print(f"\nFetched {len(posts)} posts from r/{posts[0]['subreddit']}\n")
    print("=" * 80)

    for i, post in enumerate(posts, 1):
        print(f"\n[{i}] {post['title']}")
        print(
            f"    Author: u/{post['author']} | Score: {post['score']} | Comments: {post['num_comments']}"
        )
        print(f"    Posted: {post['created_utc'].strftime('%Y-%m-%d %H:%M')}")
        print(f"    URL: {post['permalink']}")

        # Show first 200 chars of content if available
        content = post["selftext"] or post["url"]
        if content:
            preview = content[:200].replace("\n", " ")
            if len(content) > 200:
                preview += "..."
            print(f"    Content: {preview}")
        print("-" * 80)


if __name__ == "__main__":
    print("Fetching posts from r/LocalLLaMA...")

    try:
        data = fetch_subreddit("LocalLLaMA", limit=10)
        posts = parse_posts(data)
        display_posts(posts)

        # Save to JSON for further processing
        with open("reddit_posts.json", "w") as f:
            json.dump(
                [
                    {
                        k: str(v) if isinstance(v, datetime) else v
                        for k, v in post.items()
                    }
                    for post in posts
                ],
                f,
                indent=2,
            )
        print("\n✓ Posts saved to reddit_posts.json")

    except Exception as e:
        print(f"Error: {e}")
