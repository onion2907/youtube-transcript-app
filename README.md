# YouTube Transcript App

 A lightweight personal web app that takes a YouTube link and returns the full transcript using only YouTube's official captions (no audio download).

- 100% TOS-compliant: captions only
- Local caching per video ID; avoids repeated work
- Minimal, mobile-friendly UI with Share and Download .txt
- PWA installable on iPhone
- No accounts, no paid APIs, no database

## Requirements

- macOS or Linux (works on Windows with minor tweaks)
- Python 3.10+
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

- `CACHE_DIR` – override cache path (defaults to `./cache`)
- `CACHE_MAX_ITEMS` – max cached videos (default 100)

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

- Captions priority: English manual > English auto > translated to English.
- If no English captions are available, you will see: "No captions found. Ask the creator to enable subtitles!"
- Caching: transcripts saved under `cache/<video_id>/transcript.txt`.
- To clear cache: POST `/api/clear-cache`.

## Deploy (simple)

For a tiny VPS (Ubuntu):

```bash
sudo apt update && sudo apt install -y python3-venv
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


