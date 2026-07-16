# -*- coding: utf-8 -*-
"""
NewsPilot AI v2 — Flask Backend Server
- Serves news from SQLite (paginated, searchable, filterable by category)
- Runs pipeline on startup + every 6 hours via APScheduler
- Exposes /progress for live pipeline status
"""

import os
import threading
from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Paths & env ───────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, "..", ".env"))

# ── Imports after chdir ───────────────────────────────────────────────────────
from database import init_db, get_articles, get_categories, get_pipeline_state
from pipeline import run_pipeline

# ── API Keys ──────────────────────────────────────────────────────────────────
GROQ_API_KEY    = os.environ.get("GROQ_API_KEY")
NEWSAPI_KEY     = os.environ.get("NEWSAPI_KEY")      # optional

if not GROQ_API_KEY:
    raise EnvironmentError(
        "GROQ_API_KEY not found in .env — get a free key at https://console.groq.com"
    )

# ── Flask ─────────────────────────────────────────────────────────────────────
app = Flask(__name__)

CORS(app, resources={r"/*": {
    "origins": "*",
    "methods": ["GET", "POST", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization"],
}})

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


# ── Pipeline runner (thread-safe) ─────────────────────────────────────────────
_pipeline_lock = threading.Lock()

def _run_pipeline_safe():
    """Prevents overlapping pipeline runs."""
    if not _pipeline_lock.acquire(blocking=False):
        print("[Scheduler] Pipeline already running — skipping this trigger.")
        return
    try:
        run_pipeline(groq_api_key=GROQ_API_KEY, newsapi_key=NEWSAPI_KEY)
    finally:
        _pipeline_lock.release()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/news", methods=["GET"])
def get_news():
    """
    GET /api/news
    Query params:
      category  — filter by category name (default: All)
      search    — full-text keyword search
      page      — page number (default: 1)
      limit     — articles per page (default: 12)
    """
    category = request.args.get("category", "All")
    search   = request.args.get("search", "").strip() or None
    page     = int(request.args.get("page", 1))
    limit    = int(request.args.get("limit", 12))

    articles = get_articles(category=category, search=search, page=page, limit=limit)
    return jsonify({"news": articles, "page": page, "limit": limit})


@app.route("/api/categories", methods=["GET"])
def get_cats():
    """GET /api/categories — returns list of available categories."""
    return jsonify({"categories": get_categories()})


@app.route("/api/status", methods=["GET"])
def get_status():
    """
    GET /api/status
    Returns pipeline readiness and article count.
    """
    articles = get_articles(limit=1)
    return jsonify({
        "ready": len(articles) > 0,
        "pipeline": get_pipeline_state(),
    })


@app.route("/api/progress", methods=["GET"])
def get_progress():
    """
    GET /api/progress
    Returns current pipeline stage + percent for live progress bar.
    """
    return jsonify(get_pipeline_state())


@app.route("/api/refresh", methods=["POST"])
def manual_refresh():
    """
    POST /api/refresh
    Trigger a manual pipeline run (non-blocking).
    """
    t = threading.Thread(target=_run_pipeline_safe, daemon=True)
    t.start()
    return jsonify({"message": "Pipeline triggered. Check /api/progress for status."})


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Initialise SQLite tables
    init_db()
    print("[Server] SQLite database initialised.")

    # Run pipeline immediately on startup (background thread)
    print("[Server] Starting initial pipeline run...")
    threading.Thread(target=_run_pipeline_safe, daemon=True).start()

    # Schedule every 6 hours
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _run_pipeline_safe,
        trigger="interval",
        hours=6,
        id="news_refresh",
        replace_existing=True,
    )
    scheduler.start()
    print("[Server] Scheduler active — pipeline will refresh every 6 hours.")

    print("[Server] Flask starting at http://127.0.0.1:5000")
    app.run(debug=False, host="0.0.0.0", port=5000)
