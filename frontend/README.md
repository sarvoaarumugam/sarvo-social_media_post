# Sarvo Podcast Studio (Streamlit frontend)

A point-and-click UI over the pipeline — no Swagger needed. Create an episode,
then walk the tabs left to right: **Plan → Script → Audio → Image → Video →
Package → Upload**. Review and correct at every step.

## Run it (two terminals)

**Terminal 1 — backend (FastAPI):**
```
uv run uvicorn main:app --reload
```

**Terminal 2 — this UI:**
```
uv run streamlit run frontend/app.py
```

The browser opens at http://localhost:8501 automatically.

## Notes
- The UI talks to the backend at `http://127.0.0.1:8000/api/v1`.
- Generation buttons call the real AI — script/audio can take 1–3 minutes; the
  spinner is normal.
- The very first YouTube upload pops a Google login window — approve it once,
  then uploads are unattended.
