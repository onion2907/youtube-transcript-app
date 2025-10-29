# YouTube Transcript App

A lightweight personal web app that takes a YouTube link and returns the full transcript.

- Uses YouTube captions when available (fast and free)
- Falls back to offline transcription with Faster-Whisper
- Local caching per video ID; avoids repeated work
- Minimal, mobile-friendly UI with Share and Download .txt
- No accounts, no paid APIs, no database

## Requirements

- macOS or Linux (works on Windows with minor tweaks)
- Python 3.10+
- FFmpeg installed and available in PATH (required by yt-dlp)
  - macOS: `brew install ffmpeg`
- Recommended: a virtual environment

## Install

```bash
cd /Users/ajinkyaganoje/utran
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

## Configure (optional)

Environment variables:

- `MODEL_NAME` (default `base`) – Faster-Whisper model name: `tiny`, `base`, `small`, `medium`, `large-v3`, etc.
- `WHISPER_DEVICE` (default `auto`) – `auto`, `cpu`, `cuda`, or `mps` (Apple Silicon)
- `WHISPER_COMPUTE` (default `auto`) – `auto`, `int8`, `int8_float16`, `float16`, `float32`
- `CACHE_DIR` – override cache path (defaults to `./cache`)

Example (Apple Silicon, small model):

```bash
export MODEL_NAME=small
export WHISPER_DEVICE=mps
export WHISPER_COMPUTE=auto
```

## Run

```bash
python app.py
# App runs at http://localhost:5000
```

Open `http://localhost:5000` in your browser.

## Usage (Web)

1. Paste a YouTube URL.
2. Click “Get Transcript”.
3. When complete, use “Download .txt” or “Share”.

The status/about shows the running model and cache path.

## Usage (API)

- Transcribe:

```bash
curl -s -X POST http://localhost:5000/api/transcribe \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}' | jq .
```

- Download .txt (after transcribe):

```bash
curl -OJ "http://localhost:5000/api/download?video_id=dQw4w9WgXcQ"
```

- Status:

```bash
curl -s http://localhost:5000/api/status | jq .
```

## Notes

- Captions priority: English manual > English auto > translated to English. If none, the app downloads audio and transcribes locally.
- Caching: transcripts saved under `cache/<video_id>/transcript.txt`.
- First run of a new Faster-Whisper model will download weights (one-time).
- To clear a specific cache: delete `cache/<video_id>`.

## Deploy (simple)

For a tiny VPS (Ubuntu):

```bash
sudo apt update && sudo apt install -y python3-venv ffmpeg
cd /opt/yt-transcript
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
export PORT=8080
export MODEL_NAME=base
gunicorn -b 0.0.0.0:$PORT app:app
```

Then open `http://SERVER_IP:8080`.

## Troubleshooting

- If audio download fails, ensure FFmpeg is installed and in `PATH`.
- On Apple Silicon, use `WHISPER_DEVICE=mps` for hardware acceleration.
- Large/long videos may take time; the UI will show “Working…”.


