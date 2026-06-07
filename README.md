# PANELIQ

AI-powered multi-panel IIM interview simulator for CAT/MBA candidates.

This repository now contains a voice-first MVP:

- Next.js interview room with real webcam access, microphone-driven speech capture, active panelist highlighting, live subtitles, and browser speech playback.
- FastAPI backend with in-memory shared interview memory, dynamic interviewer selection, panel-style follow-up questions, and an evidence-oriented report.
- Clean fallback architecture for Groq, LangGraph, Faster Whisper, Kokoro TTS, and PostgreSQL integrations.

- Product architecture: [docs/product-architecture.md](docs/product-architecture.md)
- Existing research notebook: [tests/Feature/report-generation-and-evaluation-with-followups.ipynb](tests/Feature/report-generation-and-evaluation-with-followups.ipynb)

## Run Locally

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SUPABASE_URL="..."
export SUPABASE_SERVICE_ROLE_KEY="..."
export DEMO_USER_EMAIL="demo@paneliq.local"
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
export NEXT_PUBLIC_SUPABASE_URL="..."
export NEXT_PUBLIC_SUPABASE_ANON_KEY="..."
npm run dev
```

Open `http://localhost:3000`.

Browser notes:

- Webcam and microphone require browser permission.
- Live speech recognition works best in Chrome or Edge through the Web Speech API.
- The MVP uses browser speech synthesis for interviewer audio until Kokoro TTS is wired into the backend.
