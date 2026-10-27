# Speechly — Real-time Speech to Text

A full-stack, multilingual speech-to-text MVP built with **FastAPI, Faster-Whisper, vanilla HTML/CSS/JavaScript, and MySQL**. Audio is recorded in the browser and uploaded in short chunks; the open-source Whisper model transcribes each chunk and the dashboard stores and manages the transcript history.

## Features
- Live microphone recording with incremental transcription updates (roughly every 3.5 seconds plus model processing time).
- Multilingual Whisper recognition; Hindi and English speech are supported. Code-switching quality depends on the audio/model.
- Persistent transcript history with search, edit, delete, language label, and timestamp.
- REST API with health check and CRUD endpoints.
- Docker Compose setup with MySQL 8.

> **Honest MVP limitation:** this is near-real-time chunked transcription, not a word-by-word streaming ASR engine. Chunks are decoded independently, so a sentence split across chunks may have punctuation/context issues. Use headphones/quiet audio for best results. The first transcription can be slower because the model downloads and loads. Do not describe it as production-grade or guaranteed accurate.

## Run locally (Python + SQLite)
Requirements: Python 3.11, `ffmpeg`, and a microphone-enabled browser.

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000. SQLite is created automatically for local development. The first audio request downloads the `base` multilingual model from Hugging Face.

## Run with MySQL (recommended)
Install Docker Desktop, then run:

```bash
docker compose up --build
```
Open http://localhost:8000. Docker Compose starts MySQL and the FastAPI app. Data persists in the `mysql_data` volume.

## API endpoints
| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Health check |
| POST | `/api/transcribe?save=false` | Transcribe one audio chunk; response includes text and detected language |
| GET | `/api/transcriptions?q=hello` | List/search saved records |
| GET | `/api/transcriptions/{id}` | Read one record |
| PUT | `/api/transcriptions/{id}` | Edit transcript (`{"text":"updated words"}`) |
| DELETE | `/api/transcriptions/{id}` | Delete a record |
| POST | `/api/transcriptions/manual` | Save the final assembled transcript (`{"text":"..."}`) |

API docs are available at `/docs`.

## Publish to GitHub
Create an empty repository, then from this folder:

```bash
git init
git add .
git commit -m "Build multilingual speech-to-text app"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/speechly-speech-to-text.git
git push -u origin main
```
Do not commit real database credentials or secrets. Update the remote URL to your actual repository.

## Deployment
Deploy the Dockerfile to a container host such as Render, Railway, or another service that supports Docker. Create a managed MySQL database, set `DATABASE_URL` to its connection string, and set `WHISPER_MODEL=base`, `WHISPER_DEVICE=cpu`, and `WHISPER_COMPUTE_TYPE=int8`. Configure the service to expose its assigned `PORT` (the Docker command already respects it). Use HTTPS because browsers require a secure context for microphone access. Allow sufficient RAM and disk for the Whisper model and ffmpeg; the first request may take longer while weights are downloaded. Keep the database private and use a strong password.

## Architecture
Browser MediaRecorder → `/api/transcribe` → Faster-Whisper multilingual ASR → chunk text in UI → final transcript persisted to MySQL → searchable CRUD history.

## Suggested next improvements
- Add authentication and per-user transcript ownership before public launch.
- Store audio only if required and add a clear retention/privacy policy.
- Use a streaming ASR/WebSocket pipeline and merge overlapping chunks to improve context across boundaries.
- Add migrations (Alembic), tests, rate limits, and structured logging.
