import os
import re
import json
import hashlib
from pathlib import Path
from typing import Optional, Tuple

from flask import Flask, request, jsonify, send_file, Response

# Third-party deps
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from yt_dlp import YoutubeDL

# Transcription
from faster_whisper import WhisperModel


APP_NAME = "YouTube Transcript App"
DEFAULT_MODEL = os.environ.get("MODEL_NAME", "base")  # e.g., tiny, base, small, medium, large-v3
DEFAULT_DEVICE = os.environ.get("WHISPER_DEVICE", "auto")  # auto | cpu | cuda | mps
DEFAULT_COMPUTE = os.environ.get("WHISPER_COMPUTE", "auto")  # auto | int8 | int8_float16 | float16 | float32

BASE_DIR = Path(__file__).parent.resolve()
CACHE_DIR = Path(os.environ.get("CACHE_DIR", BASE_DIR / "cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)


app = Flask(__name__, static_url_path="/static", static_folder="static")


_whisper_model: Optional[WhisperModel] = None


def get_whisper_model() -> WhisperModel:
    global _whisper_model
    if _whisper_model is None:
        device = None if DEFAULT_DEVICE == "auto" else DEFAULT_DEVICE
        compute_type = None if DEFAULT_COMPUTE == "auto" else DEFAULT_COMPUTE
        _whisper_model = WhisperModel(
            DEFAULT_MODEL,
            device=device or "auto",
            compute_type=compute_type or "auto",
        )
    return _whisper_model


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
        "audio_file": vdir / "audio.m4a",
    }


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


def download_audio(url: str, out_file: Path) -> None:
    ydl_opts = {
        "outtmpl": str(out_file.with_suffix("") ),
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        # Add headers to avoid 403 errors
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        },
        # Add cookies and other workarounds
        "cookiesfrombrowser": None,
        "extractor_retries": 3,
        "fragment_retries": 3,
        "retries": 3,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "192",
            }
        ],
    }
    # yt-dlp will append .m4a via postprocessor
    tmp_base = out_file.with_suffix("")
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    # Ensure final file path is correct
    final = tmp_base.with_suffix(".m4a")
    if final != out_file:
        if out_file.exists():
            out_file.unlink()
        final.rename(out_file)


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
    return jsonify({
        "app": APP_NAME,
        "model": DEFAULT_MODEL,
        "device": DEFAULT_DEVICE,
        "compute": DEFAULT_COMPUTE,
        "cache_dir": str(CACHE_DIR),
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

    # Try captions first (fast + free)
    captions = try_fetch_captions(video_id)
    if captions:
        paths["transcript_txt"].write_text(captions, encoding="utf-8")
        write_meta(paths["meta_json"], {
            "video_id": video_id,
            "source": "youtube_captions",
            "model": "captions",
        })
        return jsonify({
            "video_id": video_id,
            "source": "youtube_captions",
            "model": "captions",
            "transcript": captions,
            "cached": False,
        })

    # Else, download audio then run transcription
    try:
        download_audio(url, paths["audio_file"])
    except Exception as e:
        return jsonify({"error": f"Failed to download audio: {e}"}), 500

    try:
        text, info = transcribe_audio(paths["audio_file"])
    except Exception as e:
        return jsonify({"error": f"Transcription failed: {e}"}), 500

    if not text.strip():
        return jsonify({"error": "Empty transcription result."}), 500

    paths["transcript_txt"].write_text(text, encoding="utf-8")
    meta = {
        "video_id": video_id,
        "source": "faster_whisper",
        "model": DEFAULT_MODEL,
    }
    meta.update(info or {})
    write_meta(paths["meta_json"], meta)

    return jsonify({
        "video_id": video_id,
        "source": "faster_whisper",
        "model": DEFAULT_MODEL,
        "transcript": text,
        "cached": False,
    })


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


