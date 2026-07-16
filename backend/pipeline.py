# -*- coding: utf-8 -*-
"""
NewsPilot AI v2 — News Pipeline
Replaces SerpAPI + bart-large-mnli + Pollinations + ImgBB with:
  - RSS feeds (free, async, instant)
  - NewsAPI (optional, 100 req/day free)
  - all-MiniLM-L6-v2 for deduplication (80MB vs 2GB)
  - Groq LLM for combined classification + summarization
  - og:image extraction (already scraped, no upload needed)
"""

import os
import asyncio
import aiohttp
import feedparser
import requests
import re
import time
import yaml
import json
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from groq import Groq
from sentence_transformers import SentenceTransformer, util
from database import upsert_article, update_pipeline_state

def _sanitize(article: dict) -> dict:
    """Ensure all values are SQLite-safe (str/int/float/None). Converts dicts/lists to JSON strings."""
    safe_article = {}
    for k, v in article.items():
        if isinstance(v, (dict, list)):
            safe_article[k] = json.dumps(v)
        else:
            safe_article[k] = v
    return safe_article

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RSS_SOURCES_PATH = os.path.join(BASE_DIR, "rss_sources.yaml")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
}

DEDUP_THRESHOLD = 0.82      # cosine similarity above this = duplicate
MAX_ARTICLE_AGE_HOURS = 24  # ignore articles older than this
MAX_ARTICLES_PER_FEED = 8   # cap per RSS source


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — RSS Fetcher
# ─────────────────────────────────────────────────────────────────────────────
def load_rss_sources() -> dict:
    with open(RSS_SOURCES_PATH, "r") as f:
        return yaml.safe_load(f)


def parse_rss_date(entry) -> str:
    """Parse published date from RSS entry into ISO string."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        return dt.isoformat()
    return datetime.now(timezone.utc).isoformat()


def is_recent(date_str: str, max_hours: int = MAX_ARTICLE_AGE_HOURS) -> bool:
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_hours)
        return dt > cutoff
    except Exception:
        return True  # if we can't parse, include it


def fetch_rss_feed(url: str, category: str) -> list:
    """
    Fetch and parse a single RSS feed.
    Uses requests (with browser UA) then passes content to feedparser —
    avoids 403/redirect blocks that feedparser.parse(url) hits directly.
    Returns list of raw article dicts.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12, verify=False)
        if resp.status_code != 200:
            print(f"[RSS] {url} returned {resp.status_code} — skipping")
            return []

        feed = feedparser.parse(resp.content)
        articles = []
        for entry in feed.entries[:MAX_ARTICLES_PER_FEED]:
            pub_date = parse_rss_date(entry)
            if not is_recent(pub_date):
                continue
            headline = entry.get("title", "").strip()
            if not headline:
                continue
            articles.append({
                "url":          entry.get("link", ""),
                "headline":     headline,
                "description":  BeautifulSoup(
                    entry.get("summary", "") or entry.get("description", ""),
                    "html.parser"
                ).get_text(separator=" ", strip=True)[:300],
                "category":     category,
                "source_name":  feed.feed.get("title", url),
                "published_at": pub_date,
                "image_url":    None,   # filled in by scraper
            })
        return articles
    except Exception as e:
        print(f"[RSS] Error fetching {url}: {e}")
        return []



def fetch_all_rss() -> list:
    """Fetch all RSS feeds synchronously (feedparser is sync). Returns flat article list."""
    sources = load_rss_sources()
    all_articles = []
    total_feeds = sum(len(v) for v in sources.values())
    done = 0

    for category, urls in sources.items():
        for url in urls:
            articles = fetch_rss_feed(url, category)
            all_articles.extend(articles)
            done += 1
            pct = int((done / total_feeds) * 25)  # RSS = 0-25%
            update_pipeline_state("Fetching RSS feeds", pct,
                                  articles_found=len(all_articles))
    return all_articles


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — GNews API (Optional, supplements RSS)
# ─────────────────────────────────────────────────────────────────────────────
def fetch_gnews(api_key: str) -> list:
    """Fetch from GNews (gnews.io) if key is provided. Returns raw article dicts."""
    if not api_key or api_key == "PASTE_YOUR_NEWSAPI_KEY_HERE":
        return []

    print("[GNews] Fetching top headlines...")
    articles = []

    # Map our categories to GNews categories
    cat_map = {
        "Technology": "technology", "Politics": "nation", "Business": "business",
        "Sports": "sports", "Science": "science", "Health": "health",
        "Entertainment": "entertainment", "India": "nation"
    }

    for our_cat, gnews_cat in cat_map.items():
        try:
            resp = requests.get(
                "https://gnews.io/api/v4/top-headlines",
                params={
                    "category": gnews_cat,
                    "lang": "en",
                    "max": 10,
                    "apikey": api_key,
                },
                timeout=10,
            )
            data = resp.json()
            for a in data.get("articles", []):
                if not a.get("url"):
                    continue
                articles.append({
                    "url":          a["url"],
                    "headline":     (a.get("title") or "").strip(),
                    "description":  (a.get("description") or "").strip()[:500],
                    "category":     our_cat,
                    "source_name":  a.get("source", {}).get("name", "GNews"),
                    "published_at": a.get("publishedAt", datetime.now(timezone.utc).isoformat()),
                    "image_url":    a.get("image"),
                })
        except Exception as e:
            print(f"[GNews] Error fetching {our_cat}: {e}")
    return articles


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Semantic Deduplication (all-MiniLM-L6-v2, 80MB)
# ─────────────────────────────────────────────────────────────────────────────
_model = None

def get_model() -> SentenceTransformer:
    """Lazy-load the embedding model once."""
    global _model
    if _model is None:
        print("[Dedup] Loading sentence-transformers/all-MiniLM-L6-v2...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        print("[Dedup] Model loaded.")
    return _model


def deduplicate(articles: list) -> list:
    """
    Remove near-duplicate articles using cosine similarity on headlines.
    Keeps the first occurrence of each unique article.
    """
    if not articles:
        return []

    model = get_model()
    headlines = [a["headline"] for a in articles]
    embeddings = model.encode(headlines, convert_to_tensor=True, show_progress_bar=False)

    keep = []
    kept_embeddings = []

    for i, (article, emb) in enumerate(zip(articles, embeddings)):
        is_dup = False
        for kept_emb in kept_embeddings:
            score = float(util.cos_sim(emb, kept_emb)[0][0])
            if score >= DEDUP_THRESHOLD:
                is_dup = True
                break
        if not is_dup:
            keep.append(article)
            kept_embeddings.append(emb)

    print(f"[Dedup] {len(articles)} → {len(keep)} unique articles")
    return keep


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — Article Scraping (og:image + full text)
# ─────────────────────────────────────────────────────────────────────────────
def scrape_article(url: str) -> dict:
    """
    Fetch article page, extract:
      - og:image (for thumbnail, no Pollinations/ImgBB needed)
      - full article text (for summarization)
    Returns dict or None on failure.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12, verify=False)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract og:image
        image_url = None
        for attr in [("property", "og:image"), ("name", "twitter:image")]:
            tag = soup.find("meta", {attr[0]: attr[1]})
            if tag and tag.get("content"):
                image_url = tag["content"]
                break

        # Extract full article text (paragraphs only, skip nav/footer noise)
        paragraphs = soup.find_all("p")
        text = " ".join(p.get_text(strip=True) for p in paragraphs
                        if len(p.get_text(strip=True)) > 40)

        return {"text": text[:6000], "image_url": image_url}   # cap at 6000 chars for Groq

    except Exception as e:
        print(f"[Scraper] Failed {url}: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Step 5 — Groq: Combined Classification + Summarization (one call)
# ─────────────────────────────────────────────────────────────────────────────
CATEGORIES = [
    "Technology", "Politics", "Business",
    "Sports", "Science", "Health", "Entertainment", "India"
]

GROQ_SYSTEM_PROMPT = f"""You are a professional news editor. Given a news article, return ONLY valid JSON (no markdown, no extra text) in this exact format:
{{
  "headline": "A concise, engaging headline (max 15 words)",
  "category": "One of: {', '.join(CATEGORIES)}",
  "sentiment": "One of: Positive, Neutral, Negative",
  "summary": "Three paragraphs summarizing the article. Each paragraph should be 2-3 sentences. Write in a clear, journalistic style."
}}"""


def process_with_groq(client: Groq, article_text: str, headline: str, retries: int = 3) -> dict:
    """
    Send article to Groq for combined classification + summarization.
    Returns parsed JSON dict or None on failure.
    """
    prompt = f"Headline: {headline}\n\nArticle:\n{article_text}"

    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": GROQ_SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.3,
                max_tokens=800,
            )
            raw = resp.choices[0].message.content.strip()

            # Strip markdown code fences if Groq wraps in ```json ... ```
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

            return json.loads(raw)

        except json.JSONDecodeError as e:
            print(f"[Groq] JSON parse error (attempt {attempt+1}): {e}")
        except Exception as e:
            err = str(e)
            if "401" in err or "invalid_api_key" in err:
                raise PermissionError(f"Groq API key invalid: {err}")
            if "429" in err:
                wait = 35 * (attempt + 1)
                print(f"[Groq] Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"[Groq] Error (attempt {attempt+1}): {err}")
                return None

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Main Pipeline Runner
# ─────────────────────────────────────────────────────────────────────────────
def run_pipeline(groq_api_key: str, newsapi_key: str = None):
    """
    Full v2 pipeline:
      1. Fetch RSS (all categories simultaneously)
      2. Enrich with GNews (optional)
      3. Deduplicate with all-MiniLM-L6-v2
      4. Scrape each article for full text + og:image
      5. Groq: classify + summarize in one call
      6. Save to SQLite
    """
    print("\n[Pipeline v2] ─── Starting ───")
    update_pipeline_state("Starting pipeline", 0)

    client = Groq(api_key=groq_api_key)

    # ── Step 1: RSS ──────────────────────────────────────────────────────────
    update_pipeline_state("Fetching RSS feeds", 5)
    rss_articles = fetch_all_rss()
    print(f"[Pipeline] RSS: {len(rss_articles)} raw articles")

    # ── Step 2: GNews ──────────────────────────────────────────────────────
    gnews_articles = []
    if newsapi_key:
        update_pipeline_state("Fetching GNews", 28)
        gnews_articles = fetch_gnews(newsapi_key)
        print(f"[Pipeline] GNews: {len(gnews_articles)} articles")

    all_articles = rss_articles + gnews_articles
    update_pipeline_state("Deduplicating", 32, articles_found=len(all_articles))

    if not all_articles:
        update_pipeline_state("Error", 0, error="No articles fetched from any source")
        return

    # ── Step 3: Deduplicate ──────────────────────────────────────────────────
    unique_articles = deduplicate(all_articles)
    update_pipeline_state("Scraping articles", 40,
                          articles_found=len(unique_articles))

    # ── Steps 4 & 5: Scrape + Groq process each unique article ──────────────
    saved = 0
    total = len(unique_articles)

    for idx, article in enumerate(unique_articles):
        pct = 40 + int((idx / total) * 55)  # 40% → 95%
        update_pipeline_state(
            f"Processing article {idx+1}/{total}",
            pct,
            articles_found=total,
            articles_saved=saved,
        )

        if not article.get("url"):
            continue

        # Scrape full text + og:image
        scraped = scrape_article(article["url"])
        if scraped:
            article_text = scraped["text"]
            if not article.get("image_url"):
                article["image_url"] = scraped["image_url"]
        else:
            article_text = article.get("description", "") or ""

        if not article_text.strip():
            continue

        # Truncate text to 1500 chars to prevent Groq Tokens-Per-Minute limit (429 errors)
        article_text = article_text[:1500]

        # Groq: classify + summarize
        try:
            result = process_with_groq(client, article_text, article["headline"])
        except PermissionError as e:
            print(f"[Pipeline] 🔴 FATAL auth error: {e}")
            update_pipeline_state("Error", pct, error=str(e))
            return

        if not result:
            continue

        # Merge Groq result into article dict
        article["headline"]  = result.get("headline", article["headline"])
        article["summary"]   = result.get("summary", "")
        article["category"]  = result.get("category", article.get("category", "General"))
        article["sentiment"] = result.get("sentiment", "Neutral")

        # Sanitize: SQLite only accepts str/int/float/None — convert any dict/list to str
        upsert_article(_sanitize(article))
        saved += 1

        # Throttle slightly to be kind to Groq free tier
        time.sleep(0.5)

    # ── Done ─────────────────────────────────────────────────────────────────
    update_pipeline_state("Complete", 100,
                          articles_found=total,
                          articles_saved=saved)
    print(f"\n[Pipeline v2] ✅ Done — saved {saved}/{total} articles to SQLite")
