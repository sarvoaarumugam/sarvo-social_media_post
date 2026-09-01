# Sarvo Podcast Studio

An automated content pipeline that turns a single topic into a **fully produced,
two-host podcast video published to YouTube** — plus a matching **LinkedIn post**
(caption + graphic) — with a human review checkpoint at every stage.

It's built as a resumable state machine over MongoDB: each stage (plan → script →
audio → image → video → metadata → upload) picks up where the last one left off,
so nothing is lost if a run fails partway through, and you can correct the AI's
output at any step before moving on.

## What it does

**Podcast pipeline (topic → YouTube video)**
- **Strategist blueprint** — AI plans click-worthy titles, a thumbnail concept,
  cold-open hooks, a retention-driven outline (with pattern interrupts and open
  loops), a takeaway and a CTA, *before* any script is written.
- **Two-host script generation** — a natural back-and-forth dialogue between two
  configurable hosts, targeted to a specific length (minutes → word count), with
  automatic expansion if a draft comes in short. Fully editable before moving on.
- **Text-to-speech audio** — human-sounding narration per host (distinct voices
  and personas), with natural pacing/pauses, loudness normalization, and
  per-turn timing captured for captions.
- **AI cover art + thumbnail** — a generated background image (or a fixed/preset
  image, at zero AI cost) with a branded title overlay; regenerate with your own
  feedback until it's right.
- **Video assembly** — ffmpeg renders the final 1080p MP4: image + audio, an
  optional silent intro card, burned-in animated captions (per-host colors), and
  an animated audio waveform.
- **Metadata & packaging** — SEO title, description with chapter markers, and
  tags, generated from the script and editable before upload.
- **YouTube upload** — publishes the finished video with its thumbnail and
  metadata via the YouTube Data API (OAuth desktop flow), defaulting to
  `unlisted` until you trust the pipeline.
- **Cost tracking** — per-episode cost logged for script, TTS, image and
  metadata generation.

**LinkedIn pipeline (brief → post)**
- Generate a caption from a short brief, edit it, then generate (or
  feedback-driven regenerate) a matching square graphic. Posting itself is
  manual — the pipeline prepares the ready-to-publish assets.

**Frontend**
- A Streamlit dashboard: a home view of all episodes with status/progress, a
  "Create New Video" flow, and a step-locked wizard (Plan → Script → Audio →
  Image → Video → Package → Upload) for reviewing and approving each stage.

**Prompts as data**
- Every AI prompt lives in editable YAML under [prompts/](prompts/) (strategy,
  script, audio delivery, image), with placeholders filled in at runtime — no
  code changes needed to tune tone, language, or style. See
  [prompts/README.md](prompts/README.md).

## Tech stack

| Layer | Technology |
|---|---|
| Backend API | [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/) |
| Frontend | [Streamlit](https://streamlit.io/) |
| Database / ODM | [MongoDB Atlas](https://www.mongodb.com/atlas) via [Beanie](https://beanie-odm.dev/) (built on Motor + Pydantic v2) |
| Settings | [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) (`.env`-driven) |
| AI (script, TTS, images) | [OpenAI API](https://platform.openai.com/) — GPT models, `gpt-4o-mini-tts`, `gpt-image-1` |
| Media processing | Pillow (image/overlay), pydub (audio), ffmpeg via `imageio-ffmpeg` (video assembly, captions, waveform) |
| YouTube publishing | Google API Python Client + `google-auth-oauthlib` (YouTube Data API v3, OAuth desktop flow) |
| Scheduling | APScheduler (local; AWS EventBridge planned) |
| Package/dependency management | [uv](https://docs.astral.sh/uv/) |
| Testing / linting | pytest, pytest-asyncio, httpx, ruff |

## Project structure

```
app/
  api/v1/          # FastAPI routers: episodes, linkedin, assets, health
  core/            # settings, prompt loader, LLM client, logging, pricing
  db/              # MongoDB/Beanie connection
  models/          # Beanie documents (Episode, LinkedInPost)
  schemas/         # Pydantic request/response schemas
  services/        # pipeline stages (script, tts, image, video, metadata, upload)
frontend/          # Streamlit UI
prompts/           # editable YAML prompts (see prompts/README.md)
scripts/           # one-off/dev scripts (auth, generation smoke tests)
assets/            # fixed backgrounds & preset thumbnail designs
tests/             # pytest suite
main.py            # FastAPI entrypoint
```

## Setup

**Requirements:** Python ≥ 3.12, [uv](https://docs.astral.sh/uv/), ffmpeg is
bundled (no host install needed), a MongoDB Atlas connection string, an OpenAI
API key, and (for YouTube upload) a Google Cloud OAuth **Desktop app**
client-secret JSON.

1. Install dependencies:
   ```
   uv sync
   ```
2. Copy `.env.example` to `.env` and fill in the required values
   (`OPENAI_API_KEY`, `MONGODB_URI`); everything else has a working default in
   [app/core/config.py](app/core/config.py).
3. For YouTube upload, place your Google OAuth client-secret JSON at the repo
   root (path configurable via `YOUTUBE_CLIENT_SECRET_FILE`) and run:
   ```
   uv run python scripts/youtube_auth.py
   ```
   This opens a one-time Google login and saves `token.json`; uploads are
   unattended after that.

## Run it

**Terminal 1 — backend (FastAPI):**
```
uv run uvicorn main:app --reload
```
API docs at `http://127.0.0.1:8000/docs`.

**Terminal 2 — frontend (Streamlit):**
```
uv run streamlit run frontend/app.py
```
Opens at `http://localhost:8501` and talks to the backend at
`http://127.0.0.1:8000/api/v1`.

## Tests

```
uv run pytest
```
