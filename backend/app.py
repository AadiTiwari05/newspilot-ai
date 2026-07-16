from flask import Flask, jsonify
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})



# Ensure correct path for News.json, assuming it's in the same directory as app.py
NEWS_FILE = os.path.join(os.path.dirname(__file__), "News.json")

@app.route("/news", methods=["GET"])
def get_news():
    if not os.path.exists(NEWS_FILE):
        return jsonify({"error": "News file not found"}), 404

    with open(NEWS_FILE, "r", encoding="utf-8") as file:
        try:
            news_data = json.load(file)
        except json.JSONDecodeError:
            return jsonify({"error": "Invalid JSON format"}), 500

    return jsonify(news_data)

if __name__ == "__main__":
    app.run(debug=True)  # Change to debug=False in production
