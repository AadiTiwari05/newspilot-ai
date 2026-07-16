# -*- coding: utf-8 -*-
"""
NewsPilot AI - Flask Backend Server
Runs the full AI news pipeline then serves results via /news endpoint.
"""

from SRC.Summary_Generator import NewsAgent1, NewsAgent2
from SRC.Prompts import system_prompt, merge_prompt
from SRC.Helper_func import NewsFilter, NewsClassifier, ImgBBUploader

import os
import yaml
import requests
import json
import threading
import pandas as pd
from PIL import Image
from io import BytesIO
from flask import Flask, jsonify, make_response
from flask_cors import CORS
from dotenv import load_dotenv

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)  # ensure CWD is always the backend folder

# Load .env from the parent directory (newspilot-ai/)
load_dotenv(os.path.join(BASE_DIR, '..', '.env'))

# Disable SSL verification warnings (scraping workaround — scoped to this module)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Flask app ────────────────────────────────────────────────────────────────
app = Flask(__name__)

# Layer 1: flask-cors handles the standard preflight and response headers
CORS(app, resources={r"/*": {
    "origins": "*",
    "methods": ["GET", "POST", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization"],
}})

# Layer 2: manual after_request hook — belt-and-suspenders guarantee that
# CORS headers are present on EVERY response, including error responses.
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

NEWS_FILE = os.path.join(BASE_DIR, "News.json")
IMAGES_DIR = os.path.join(BASE_DIR, "Images")

# ── Load config ──────────────────────────────────────────────────────────────
config_path = os.path.join(BASE_DIR, 'configs.yaml')
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

config_topic = config['topic']
config_location = config['location']

# ── Validate API keys ─────────────────────────────────────────────────────────
groq_api_key = os.environ.get("GROQ_API_KEY")
serp_api_key = os.environ.get("SERP_API_KEY")
imgBB_api_key = os.environ.get("IMGBB_API_KEY")

if not groq_api_key:
    raise EnvironmentError("GROQ_API_KEY not found. Make sure your .env file is set up correctly.")
if not serp_api_key:
    raise EnvironmentError("SERP_API_KEY not found. Make sure your .env file is set up correctly.")
if not imgBB_api_key:
    raise EnvironmentError("IMGBB_API_KEY not found. Make sure your .env file is set up correctly.")


# ── Pipeline ──────────────────────────────────────────────────────────────────
def run_pipeline():
    """
    Full AI pipeline:
      1. Fetch news with NewsAgent1
      2. Filter unique articles with BERT (NewsFilter)
      3. For each unique article, deep-search + summarize + merge (NewsAgent2)
      4. Classify summaries (NewsClassifier)
      5. Generate images (Pollinations AI) and upload (ImgBB)
      6. Save to News.json
    """
    print("[Pipeline] Starting news pipeline...")

    # ── Step 1: Fetch initial news ───────────────────────────────────────────
    agent1 = NewsAgent1(
        system_prompt=system_prompt,
        location=config_location,
        topic=config_topic,
        gemini_api_key=groq_api_key,
        serp_api_key=serp_api_key,
    )
    print(f"[Pipeline] Searching topic: '{config_topic}' in '{config_location}'")
    news_df = agent1.process_news(num_links=8)
    print(f"[Pipeline] Fetched {news_df.shape[0]} articles")

    if news_df.empty:
        print("[Pipeline] No articles fetched. Aborting.")
        return

    # Use positional-safe Series
    full_text_series = news_df['full_text'].reset_index(drop=True)

    descriptions = []
    for item in full_text_series:
        if item and item.get('description'):
            descriptions.append(item['description'])
        else:
            descriptions.append("")

    # ── Step 2: Filter unique articles ───────────────────────────────────────
    news_filter = NewsFilter(threshold=0.75)
    unique_news_indices = news_filter.filter_unique_texts(descriptions)
    print(f"[Pipeline] Unique article indices: {unique_news_indices}")

    if not unique_news_indices:
        print("[Pipeline] No unique articles found. Aborting.")
        return

    # ── Step 3: Deep search + summarize each unique article ──────────────────
    news_summaries = []         # (summary_text, original_index) pairs
    for i in unique_news_indices:
        article_topic = full_text_series[i]['description']
        print(f"[Pipeline] Processing article: {article_topic[:80]}...")
        try:
            agent2 = NewsAgent2(
                merge_prompt=merge_prompt,
                system_prompt=system_prompt,
                topic=article_topic,
                gemini_api_key=groq_api_key,
                serp_api_key=serp_api_key,
                similarity_threshold=0.75
            )
            summary = agent2.process_news(num_links=4)
            if summary:
                news_summaries.append(summary)
                print(f"[Pipeline] ✅ Summary generated for article index {i}")
            else:
                print(f"[Pipeline] ⚠️  Skipping article index {i} — summary was empty (scraping/similarity may have failed)")
        except PermissionError as e:
            # 401 Invalid API Key — abort immediately, no point continuing
            print(f"\n[Pipeline] 🔴 FATAL: {e}")
            print("[Pipeline] Aborting pipeline. Fix GROQ_API_KEY in .env and restart server.py.")
            return
        except Exception as e:
            print(f"[Pipeline] ⚠️  Error processing article index {i}: {e} — skipping.")
            continue

    print(f"[Pipeline] Generated {len(news_summaries)} valid summaries out of {len(unique_news_indices)} unique articles")

    if not news_summaries:
        print("[Pipeline] No valid summaries produced. Check your API key and network connection. Aborting.")
        return

    # ── Step 4: Classify articles ─────────────────────────────────────────────
    classifier = NewsClassifier()
    results_df = classifier.classify_multiple(news_summaries)

    # ── Step 5: Generate and upload images ────────────────────────────────────
    os.makedirs(IMAGES_DIR, exist_ok=True)  # BUG-10 fix: ensure directory exists

    image_urls = []
    for idx, i in enumerate(unique_news_indices):
        prompt = full_text_series[i]["description"]
        api_url = f"https://image.pollinations.ai/prompt/{prompt}"

        try:
            response = requests.get(api_url, timeout=30)
            if response.status_code == 200:
                image = Image.open(BytesIO(response.content))
                width, height = image.size
                crop_area = (0, 0, width, height - 60)
                cropped_image = image.crop(crop_area)
                img_path = os.path.join(IMAGES_DIR, f"{idx}.jpg")
                cropped_image.save(img_path)

                # Upload to ImgBB
                uploader = ImgBBUploader(api_key=imgBB_api_key)
                result = uploader.upload_image(img_path)
                if result:
                    image_urls.append(result['direct_url'])
                else:
                    image_urls.append("")
            else:
                print(f"[Pipeline] Image generation failed for idx {idx}, status: {response.status_code}")
                image_urls.append("")
        except Exception as e:
            print(f"[Pipeline] Image error for idx {idx}: {e}")
            image_urls.append("")

    results_df['image_urls'] = image_urls

    # ── Step 6: Save results ──────────────────────────────────────────────────
    out = results_df.drop(columns=['all_scores', 'confidence'])
    new_news_path = os.path.join(BASE_DIR, 'New_News.json')
    out.to_json(new_news_path, orient='records', indent=4)

    _merge_json_files()
    print("[Pipeline] Pipeline complete! Flask is ready to serve news.")


def _merge_json_files():
    """
    Merge New_News.json into News_list.json (cumulative history),
    then write the combined data to News.json for the API.
    Uses absolute paths — BUG-08 fix.
    """
    new_news_path = os.path.join(BASE_DIR, 'New_News.json')
    news_list_path = os.path.join(BASE_DIR, 'News_list.json')

    # Initialize News_list.json if missing
    if not os.path.exists(news_list_path):
        with open(news_list_path, 'w') as f:
            json.dump([], f)

    try:
        df_new = pd.read_json(new_news_path)
        df_existing = pd.read_json(news_list_path)

        merged_df = pd.concat([df_new, df_existing], ignore_index=True)
        merged_df.to_json(news_list_path, orient='records', indent=4)

        wrapped_data = {"news": merged_df.to_dict(orient='records')}
        with open(NEWS_FILE, 'w') as f:
            json.dump(wrapped_data, f, indent=4)

        print(f"[Pipeline] Merged {len(df_new)} new + {len(df_existing)} existing articles → News.json")
    except Exception as e:
        print(f"[Pipeline] Error merging JSON files: {e}")


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/news", methods=["GET"])
def get_news():
    if not os.path.exists(NEWS_FILE):
        return jsonify({"error": "News file not found. Pipeline may still be running."}), 404

    with open(NEWS_FILE, "r", encoding="utf-8") as f:
        try:
            news_data = json.load(f)
        except json.JSONDecodeError:
            return jsonify({"error": "Invalid JSON format in News.json"}), 500

    return jsonify(news_data)


@app.route("/status", methods=["GET"])
def get_status():
    """Check if the pipeline has finished and news is available."""
    ready = os.path.exists(NEWS_FILE)
    return jsonify({"ready": ready, "news_file": NEWS_FILE if ready else None})


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # BUG-07 fix: run pipeline in background thread so Flask starts immediately
    print("[Server] Starting background pipeline thread...")
    pipeline_thread = threading.Thread(target=run_pipeline, daemon=True)
    pipeline_thread.start()

    print("[Server] Flask starting at http://127.0.0.1:5000")
    app.run(debug=False, host="0.0.0.0", port=5000)
