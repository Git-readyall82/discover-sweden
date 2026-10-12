import json
import re
import time
import urllib.parse
import urllib.request
from collections import defaultdict, deque
from pathlib import Path

import boto3
from flask import Flask, jsonify, request, send_from_directory

REGION = "eu-north-1"
MODEL_ID = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
BASE = Path(__file__).parent

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.json.ensure_ascii = False
bedrock = boto3.client("bedrock-runtime", region_name=REGION)

ENTRIES = json.loads((BASE / "data" / "entries.json").read_text(encoding="utf-8"))
BY_ID = {e["id"]: e for e in ENTRIES}
CATALOG = "\n".join(f'{e["id"]} | {e["name"]} | {e["category"]}' for e in ENTRIES)

SYSTEM_PROMPT = (
    "You are 'Discover Sweden', a friendly guide to Swedish places, scientists, inventors, "
    "food, traditions, brands and musicians.\n"
    "Answer the user's question in 2-4 short sentences, in the same language as the question "
    "(English or Swedish). Only talk about Sweden; if the question is off-topic, politely steer back.\n"
    "Below is a curated catalogue (id | name | category). Pick up to 4 entries that are most "
    "relevant to your answer and return their ids. Only use ids from the catalogue. "
    "If none fit, return an empty list.\n"
    "Reply with ONLY a JSON object, no other text: "
    '{"answer": "<your answer>", "ids": ["id1", "id2"]}\n\n'
    "CATALOGUE:\n" + CATALOG
)

# --- simple rate limit: 20 questions per 10 minutes per visitor ---
HITS = defaultdict(deque)
LIMIT, WINDOW = 20, 600


def client_ip():
    fwd = request.headers.get("X-Forwarded-For", "")
    return fwd.split(",")[0].strip() if fwd else request.remote_addr


def too_many(ip):
    now = time.time()
    q = HITS[ip]
    while q and now - q[0] > WINDOW:
        q.popleft()
    if len(q) >= LIMIT:
        return True
    q.append(now)
    return False


# --- Wikipedia summary (picture, text, link), cached when it succeeds ---
WIKI_CACHE = {}


def wiki_url(title):
    return "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))


def wiki_summary(title):
    if title in WIKI_CACHE:
        return WIKI_CACHE[title]
    api = ("https://en.wikipedia.org/api/rest_v1/page/summary/"
           + urllib.parse.quote(title.replace(" ", "_"), safe=""))
    req = urllib.request.Request(api, headers={"User-Agent": "DiscoverSweden/1.0 (school project)"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            d = json.load(r)
    except Exception:
        return {"extract": "", "image": None, "url": None}
    info = {
        "extract": d.get("extract", ""),
        "image": (d.get("thumbnail") or {}).get("source"),
        "url": d.get("content_urls", {}).get("desktop", {}).get("page"),
    }
    WIKI_CACHE[title] = info
    return info


def card(entry):
    info = wiki_summary(entry["wiki"])
    return {
        "id": entry["id"],
        "name": entry["name"],
        "category": entry["category"],
        "extract": info["extract"],
        "image": info["image"],
        "url": info["url"] or wiki_url(entry["wiki"]),
    }


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/entries")
def entries():
    return jsonify([{"id": e["id"], "name": e["name"], "category": e["category"]} for e in ENTRIES])


@app.get("/api/card/<entry_id>")
def get_card(entry_id):
    e = BY_ID.get(entry_id)
    if not e:
        return jsonify({"error": "not found"}), 404
    return jsonify(card(e))


@app.post("/api/ask")
def ask():
    if too_many(client_ip()):
        return jsonify({"error": "Too many questions, please wait a few minutes."}), 429
    data = request.get_json(silent=True) or {}
    question = str(data.get("question", "")).strip()
    if not question or len(question) > 500:
        return jsonify({"error": "Please write a question (max 500 characters)."}), 400
    try:
        resp = bedrock.converse(
            modelId=MODEL_ID,
            system=[{"text": SYSTEM_PROMPT}],
            messages=[{"role": "user", "content": [{"text": question}]}],
            inferenceConfig={"maxTokens": 600, "temperature": 0.3},
        )
        text = resp["output"]["message"]["content"][0]["text"]
    except Exception as exc:
        app.logger.error("Bedrock error: %s", exc)
        return jsonify({"error": "The AI service is unavailable right now."}), 502
    answer, ids = text, []
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            parsed = json.loads(m.group(0))
            answer = str(parsed.get("answer", text))
            ids = [i for i in parsed.get("ids", []) if i in BY_ID]
            ids = list(dict.fromkeys(ids))[:4]
        except Exception:
            pass
    return jsonify({"answer": answer, "cards": [card(BY_ID[i]) for i in ids]})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
