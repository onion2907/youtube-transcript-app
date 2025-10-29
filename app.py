import os
import re
import json
from pathlib import Path
from typing import Optional, Tuple

from flask import Flask, request, jsonify, send_file, Response
import requests

# Third-party deps
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
 


APP_NAME = "YouTube Transcript App"
CACHE_MAX_ITEMS = int(os.environ.get("CACHE_MAX_ITEMS", "100"))
BROWSERLESS_TOKEN = os.environ.get("BROWSERLESS_TOKEN")

BASE_DIR = Path(__file__).parent.resolve()
CACHE_DIR = Path(os.environ.get("CACHE_DIR", BASE_DIR / "cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)


app = Flask(__name__, static_url_path="/static", static_folder="static")


def extract_video_id(url: str) -> Optional[str]:
    # Support youtube.com/watch?v=, youtu.be/, and shorts
    patterns = [
        r"(?:v=)([A-Za-z0-9_-]{11})",
        r"youtu\.be/([A-Za-z0-9_-]{11})",
        r"youtube\.com/shorts/([A-Za-z0-9_-]{11})",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


def cache_paths(video_id: str) -> dict:
    vdir = CACHE_DIR / video_id
    vdir.mkdir(parents=True, exist_ok=True)
    return {
        "dir": vdir,
        "caption_txt": vdir / "captions.txt",
        "transcript_txt": vdir / "transcript.txt",
        "meta_json": vdir / "meta.json",
    }


def cleanup_cache(max_items: int = CACHE_MAX_ITEMS) -> dict:
    # Keep at most max_items subdirectories in CACHE_DIR by mtime
    if not CACHE_DIR.exists():
        return {"kept": 0, "removed": 0}
    entries = [p for p in CACHE_DIR.iterdir() if p.is_dir()]
    entries.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    kept = entries[:max_items]
    removed = entries[max_items:]
    removed_count = 0
    for d in removed:
        try:
            for sub in d.rglob('*'):
                if sub.is_file():
                    sub.unlink(missing_ok=True)
            d.rmdir()
            removed_count += 1
        except Exception:
            # best effort; ignore
            pass
    return {"kept": len(kept), "removed": removed_count}


def write_meta(meta_path: Path, meta: dict) -> None:
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def load_meta(meta_path: Path) -> dict:
    if meta_path.exists():
        return json.loads(meta_path.read_text(encoding="utf-8"))
    return {}


def try_fetch_captions(video_id: str) -> Optional[str]:
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    except TranscriptsDisabled:
        return None
    except NoTranscriptFound:
        return None
    except Exception:
        return None

    # Prefer English manual, then English auto-generated, then translate-to-English
    candidates = []
    try:
        if transcript_list.find_manually_created_transcript(["en"]):
            candidates.append(transcript_list.find_manually_created_transcript(["en"]))
    except Exception:
        pass
    try:
        if transcript_list.find_generated_transcript(["en"]):
            candidates.append(transcript_list.find_generated_transcript(["en"]))
    except Exception:
        pass

    # If nothing in English, try translating any available to English
    if not candidates:
        try:
            for t in transcript_list:
                if t.is_translatable:
                    candidates.append(t.translate("en"))
                    break
        except Exception:
            pass

    for t in candidates:
        try:
            data = t.fetch()
            text = "\n".join([item.get("text", "").replace("\n", " ").strip() for item in data if item.get("text")])
            if text.strip():
                return text
        except Exception:
            continue
    return None


def transcribe_audio(audio_path: Path) -> Tuple[str, dict]:
    model = get_whisper_model()
    segments, info = model.transcribe(
        str(audio_path),
        language="en",
        vad_filter=True,
        beam_size=5,
    )
    parts = []
    for seg in segments:
        parts.append(seg.text.strip())
    text = " ".join(parts).strip()
    meta = {
        "duration": getattr(info, "duration", None),
        "language": getattr(info, "language", "en"),
        "model_name": DEFAULT_MODEL,
    }
    return text, meta


@app.get("/api/status")
def status():
    # Cache stats
    total = 0
    if CACHE_DIR.exists():
        total = len([p for p in CACHE_DIR.iterdir() if p.is_dir()])
    return jsonify({
        "app": APP_NAME,
        "cache_dir": str(CACHE_DIR),
        "cache_items": total,
        "captions_only": True,
        "browserless": bool(BROWSERLESS_TOKEN),
        "running": True,
    })


@app.post("/api/transcribe")
def api_transcribe():
    data = request.get_json(silent=True) or {}
    url = data.get("url") or request.form.get("url")
    if not url:
        return jsonify({"error": "Missing 'url'"}), 400

    video_id = extract_video_id(url)
    if not video_id:
        return jsonify({"error": "Could not parse YouTube video ID from URL."}), 400

    paths = cache_paths(video_id)

    # If we already have a transcript, return it
    if paths["transcript_txt"].exists():
        text = paths["transcript_txt"].read_text(encoding="utf-8")
        meta = load_meta(paths["meta_json"]) or {}
        return jsonify({
            "video_id": video_id,
            "source": meta.get("source", "cache"),
            "model": meta.get("model", DEFAULT_MODEL),
            "transcript": text,
            "cached": True,
        })

    # Captions-only flow
    captions = try_fetch_captions(video_id)
    if captions:
        paths["transcript_txt"].write_text(captions, encoding="utf-8")
        write_meta(paths["meta_json"], {
            "video_id": video_id,
            "source": "youtube_captions",
            "mode": "captions_only",
        })
        return jsonify({
            "video_id": video_id,
            "source": "youtube_captions",
            "mode": "captions_only",
            "transcript": captions,
            "cached": False,
        })
    # No captions available
    return jsonify({
        "error": "No captions found. Ask the creator to enable subtitles!",
        "error_code": "NO_CAPTIONS",
    }), 404


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.post("/api/clear-cache")
def clear_cache():
    stats = cleanup_cache(max_items=0)
    return jsonify({"cleared": stats.get("removed", 0)})


def scrape_tactiq_via_browserless(video_url: str) -> Optional[str]:
    if not BROWSERLESS_TOKEN:
        return None
    endpoint = f"https://chrome.browserless.io/playwright?token={BROWSERLESS_TOKEN}"
    code = f"""
    const { chromium } = require('playwright');
    const browser = await chromium.launch();
    const page = await browser.newPage();
    await page.goto('https://tactiq.io/tools/youtube-transcript', {{ waitUntil: 'domcontentloaded' }});
    await page.waitForTimeout(1500);
    const input = await page.locator('input[type="url"], input');
    await input.fill('{video_url.replace("'", "\\'")}');
    const btn = await page.locator('button:has-text("Get Video Transcript")');
    await btn.click();
    await page.waitForTimeout(3000);
    const possible = ['pre', 'textarea', '[data-transcript]', '.transcript', '.output'];
    let text = '';
    for (const sel of possible) {{
      const el = await page.$(sel);
      if (el) {{ text = (await el.innerText()).trim(); if (text) break; }}
    }}
    if (!text) {{ text = (await page.content()); }}
    await browser.close();
    return text;
    """
    payload = {"code": code}
    r = requests.post(endpoint, json=payload, timeout=90)
    if r.status_code != 200:
        return None
    try:
        data = r.json()
        # Browserless returns { data: '<string>' } or raw text
        if isinstance(data, dict) and 'data' in data:
            return str(data['data'])
        return r.text
    except Exception:
        return r.text


@app.post('/api/tactiq')
def api_tactiq():
    body = request.get_json(silent=True) or {}
    url = body.get('url') or ''
    if not url:
        return jsonify({"error": "Missing 'url'"}), 400
    if not BROWSERLESS_TOKEN:
        return jsonify({"error": "BROWSERLESS_TOKEN not configured.", "error_code": "NO_BROWSERLESS"}), 400
    text = scrape_tactiq_via_browserless(url)
    if not text:
        return jsonify({"error": "Failed to fetch transcript from Tactiq.", "error_code": "TACTIQ_FAIL"}), 502
    return jsonify({"transcript": text, "source": "tactiq"})


@app.get("/api/download")
def api_download():
    video_id = request.args.get("video_id")
    if not video_id:
        return jsonify({"error": "Missing 'video_id'"}), 400
    paths = cache_paths(video_id)
    if not paths["transcript_txt"].exists():
        return jsonify({"error": "Transcript not found. Generate it first."}), 404
    return send_file(
        paths["transcript_txt"],
        mimetype="text/plain",
        as_attachment=True,
        download_name=f"{video_id}.txt",
    )


@app.get("/")
def index():
    # Serve static index.html
    index_path = BASE_DIR / "static" / "index.html"
    if not index_path.exists():
        return Response("Frontend not found.", status=404)
    return app.send_static_file("index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_ENV") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)


