# PANELIQ — AI-Powered IIM MBA Interview Simulator

<div align="center">

![PANELIQ](https://img.shields.io/badge/PANELIQ-AI%20Interview%20Simulator-6C63FF?style=for-the-badge&logo=openai&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-000000?style=for-the-badge&logo=next.js&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-LLaMA%203.3%2070B-F55036?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6?style=for-the-badge&logo=typescript&logoColor=white)

**Realistic, adaptive multi-panel IIM interview simulations powered by Groq LLaMA 3.3 70B — with AI-driven question sequencing, voice synthesis, and report-based progress tracking.**

[Features](#-unique-selling-points) · [Architecture](#-high-level-architecture) · [AI Workflow](#-ai-interview-workflow) · [Database](#-database-schema) · [Setup](#-local-development-setup)

</div>

---

## 📌 Overview

PANELIQ simulates IIM MBA admissions panel interviews. A candidate uploads their resume, and three AI-driven panelists — each with a distinct evaluation focus — interrogate them using a shared memory that grows dynamically throughout the interview. The system generates a detailed scored report, coaching plan, and progress benchmarks across multiple sessions.

---

## ✨ Unique Selling Points

| USP | Description |
|-----|-------------|
| **Multi-Panel AI** | Three distinct AI interviewers (Academic, Pressure, MBA) — each with a unique interrogation lens — share a live memory of the candidate |
| **Adaptive, Non-Sequential Questions** | Speaker selection is AI-driven based on memory signals (contradictions, follow-ups, depth gaps) — not a round-robin queue |
| **Depth Laddering** | Each topic is probed progressively through 5 depth levels (e.g., problem → architecture → decisions → tradeoffs → business impact) |
| **Smart Contradiction Detection** | Prof. Arvind Menon (Pressure panelist) is triggered automatically when conflicting claims are detected across answers |
| **Voice Interface** | Faster-Whisper transcribes candidate audio; Kokoro TTS speaks interviewer questions with distinct voice personas |
| **PDF Resume Parsing** | PyMuPDF extracts resume text; Groq LLM builds a structured candidate profile for grounding all questions |
| **Scored Evaluation Report** | Multi-dimensional scoring across Communication, Leadership, Business Awareness, Academic Depth, Career Clarity with IIM benchmark comparison |
| **Cross-Session Progress Tracking** | Dimension score deltas, recurring weakness detection, and trend analysis across all past interviews |
| **Session Report Comparison** | Side-by-side comparison of two sessions with benchmark gap analysis (Average CAT Aspirant → Strong IIM ABC Candidate) |
| **Coaching Plans** | AI-generated follow-up questions, ideal answer frameworks, and practice tracking per weakness |

---

## 🛠 Technology Stack

### Backend

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **API Framework** | [FastAPI 0.115](https://fastapi.tiangolo.com/) | REST API, request validation, dependency injection |
| **Runtime** | [Uvicorn 0.34](https://www.uvicorn.org/) | ASGI server |
| **Data Validation** | [Pydantic 2.10](https://docs.pydantic.dev/) | Request/response schemas, domain models |
| **AI Inference** | [Groq SDK 0.13 + LLaMA 3.3 70B](https://groq.com/) | Question generation, memory updates, report synthesis |
| **LLM Orchestration** | [LangGraph 0.2](https://www.langchain.com/langgraph) | Agentic state management |
| **Speech-to-Text** | [Faster-Whisper 1.1](https://github.com/SYSTRAN/faster-whisper) | Candidate audio transcription |
| **Text-to-Speech** | [Kokoro 0.9](https://github.com/hexgrad/kokoro) | Interviewer voice synthesis (3 distinct voices) |
| **PDF Parsing** | [PyMuPDF 1.25](https://pymupdf.readthedocs.io/) | Resume text extraction |
| **Database Client** | [supabase-py 2.10](https://github.com/supabase-community/supabase-py) | Supabase REST + Auth integration |
| **Environment** | [python-dotenv](https://github.com/theskumar/python-dotenv) | `.env` loading |

### Frontend

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Framework** | [Next.js 16](https://nextjs.org/) + [React 19](https://react.dev/) | UI rendering, SSR, routing |
| **Language** | [TypeScript 5.7](https://www.typescriptlang.org/) | Type-safe frontend code |
| **Styling** | [Tailwind CSS 3.4](https://tailwindcss.com/) | Utility-first CSS |
| **Charts** | [Recharts 3.8](https://recharts.org/) | Score trend charts, dimension radar |
| **Icons** | [Lucide React 0.468](https://lucide.dev/) | UI icons |
| **Auth** | [@supabase/supabase-js 2.107](https://supabase.com/docs/reference/javascript) | Auth, session management |
| **Utilities** | [clsx 2.1](https://github.com/lukeed/clsx) | Conditional class names |

### Infrastructure

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Database** | [Supabase (PostgreSQL)](https://supabase.com/) | Interview data, user profiles, reports |
| **Auth** | [Supabase Auth](https://supabase.com/auth) | JWT, OAuth providers |
| **Storage** | [Supabase Storage](https://supabase.com/storage) | Resume file storage |
| **Audio Storage** | Local filesystem (`/generated_audio/`) | Kokoro-generated `.wav` files |

---

## 📂 Project Structure

```
paneliq/
├── backend/
│   ├── app/
│   │   ├── __init__.py          # Package marker
│   │   ├── main.py              # FastAPI app, all REST endpoints, PDF renderer
│   │   ├── orchestrator.py      # Session lifecycle: create → start → turn → end → report
│   │   ├── intelligence.py      # Core AI engine: profile parsing, question generation, memory, report, coaching
│   │   ├── models.py            # Pydantic domain models (all request/response/memory shapes)
│   │   ├── database.py          # Supabase repository: CRUD for sessions, memory, reports, progress
│   │   ├── interviewers.py      # Panelist definitions (Academic, Pressure, MBA)
│   │   ├── voice.py             # Faster-Whisper (STT) + Kokoro (TTS) voice services
│   │   ├── resume.py            # PyMuPDF resume text extraction
│   │   └── demo.py              # Demo-mode seeded data
│   ├── generated_audio/         # Kokoro TTS output (.wav files, served via /audio)
│   └── requirements.txt
│
├── frontend/
│   ├── app/
│   │   ├── layout.tsx           # Root HTML layout, Google Fonts, metadata
│   │   ├── page.tsx             # Single-page application (onboarding → interview → report)
│   │   └── globals.css          # Design system tokens, Tailwind layers
│   ├── components/
│   │   ├── InterviewRoom.tsx    # Real-time interview UI: audio recording, subtitle panel, turn flow
│   │   ├── InterviewerCard.tsx  # Panelist avatar with active state
│   │   ├── CandidateCamera.tsx  # Webcam feed with live status overlay
│   │   ├── ScoreChart.tsx       # Recharts radar/bar score visualisation
│   │   ├── ScoreBadge.tsx       # Coloured score badge component
│   │   ├── BenchmarkTable.tsx   # IIM benchmark comparison table
│   │   ├── DimensionGrid.tsx    # Dimension score grid with evidence
│   │   ├── CoachingCard.tsx     # Coaching item with follow-up question and ideal answer
│   │   ├── ReportDownloadButton.tsx  # PDF report download trigger
│   │   ├── SessionTimer.tsx     # 25-minute countdown timer
│   │   └── SubtitlePanel.tsx    # Live subtitle text display
│   ├── lib/                     # API client, Supabase client utilities
│   ├── package.json
│   ├── tailwind.config.ts
│   └── tsconfig.json
│
├── supabase/
│   ├── schema.sql               # Full PostgreSQL schema (16 tables)
│   ├── seed_demo_account.sql    # Demo user seed data
│   └── migrations/              # Version-controlled schema migrations
│
├── tests/                       # Test suite
├── docs/                        # Additional documentation
├── .env                         # Root environment variables (shared backend)
└── README.md
```

---

## 🏗 High-Level Architecture

```mermaid
graph TB
    subgraph "Browser (Next.js 16 / React 19)"
        UI["Interview UI<br/>page.tsx"]
        IR["InterviewRoom.tsx<br/>Audio Capture / Playback"]
        SC["ScoreChart + BenchmarkTable<br/>Report View"]
        AUTH["Supabase Auth<br/>JWT Session"]
    end

    subgraph "Backend (FastAPI + Uvicorn)"
        API["REST API<br/>main.py"]
        ORC["Orchestrator<br/>orchestrator.py"]
        INTEL["AI Intelligence Engine<br/>intelligence.py"]
        VOICE["Voice Service<br/>voice.py"]
        REPO["Supabase Repository<br/>database.py"]
    end

    subgraph "AI Layer"
        GROQ["Groq Cloud<br/>LLaMA 3.3 70B"]
        WHISPER["Faster-Whisper<br/>(local, CPU/GPU)"]
        KOKORO["Kokoro TTS<br/>(local)"]
    end

    subgraph "Supabase (PostgreSQL)"
        DB_USER["users / user_profiles"]
        DB_RESUME["resumes / candidate_profiles"]
        DB_SESSION["interview_sessions / interview_turns"]
        DB_MEMORY["interview_memory"]
        DB_REPORT["reports / report_scores"]
        DB_PROGRESS["progress_snapshots"]
        DB_COACHING["followup_questions / coaching_plans"]
    end

    UI -->|"REST + Bearer JWT"| API
    IR -->|"POST /speech/transcribe (audio blob)"| API
    AUTH -->|"Supabase JWT"| API

    API --> ORC
    ORC --> INTEL
    ORC --> VOICE
    ORC --> REPO

    INTEL -->|"JSON chat completions"| GROQ
    VOICE -->|"transcribe audio"| WHISPER
    VOICE -->|"synthesize WAV"| KOKORO
    KOKORO -->|"/audio/*.wav"| IR

    REPO <-->|"supabase-py"| DB_USER
    REPO <-->|"supabase-py"| DB_RESUME
    REPO <-->|"supabase-py"| DB_SESSION
    REPO <-->|"supabase-py"| DB_MEMORY
    REPO <-->|"supabase-py"| DB_REPORT
    REPO <-->|"supabase-py"| DB_PROGRESS
    REPO <-->|"supabase-py"| DB_COACHING

    SC -->|"GET /reports/compare"| API
```

---

## 🤖 AI Interview Workflow

### How Questions Are Asked — Non-Sequential, Memory-Driven

PANELIQ does **not** follow a fixed question script. Every question is determined dynamically based on the shared interview memory, candidate answers, and panelist-specific signals.

```mermaid
flowchart TD
    START([Candidate starts session]) --> OPEN_Q[Academic opens with\nresume-grounded question]
    OPEN_Q --> CANDIDATE_ANSWER[Candidate answers]

    CANDIDATE_ANSWER --> UPDATE_MEM[intelligence.update_memory\nGroq extracts:\n• Topics covered\n• Claims made\n• Strengths / Weaknesses\n• Contradictions\n• Follow-up opportunities]

    UPDATE_MEM --> CHECK_END{Turn ≥ 12\nor 25 min\nor candidate wants to end\nor sufficient depth?}
    CHECK_END -- Yes --> CLOSE[MBA panelist closes\nwith summary statement]
    CLOSE --> REPORT[Generate Report]

    CHECK_END -- No --> SPEAKER_SELECT[intelligence.select_speaker]

    SPEAKER_SELECT --> FORCED{Silent panelist\nbefore turn 3?}
    FORCED -- Yes --> FORCE_SPEAKER[Force silent panelist\nin priority: MBA → Pressure → Academic]

    FORCED -- No --> GROQ_SELECT[Groq selects speaker\nbased on:\n• Contradiction signals → Pressure\n• Follow-up queue → Suggested panelist\n• Open topic depth gaps → Relevant panelist\n• Turn-count balance]

    FORCE_SPEAKER --> GEN_Q
    GROQ_SELECT --> GEN_Q[intelligence.generate_question\nGroq generates one question:\n• Topic depth ladder applied\n• Banned patterns checked\n• Every 3rd turn: conversational bridge\n• Fallback if Groq returns bad output]

    GEN_Q --> ACCEPT{Question acceptable?\n• Not semantically similar to prior?\n• No verbatim candidate speech?\n• No filler patterns?}
    ACCEPT -- No --> ALT_Q[Generate alternative question\nfrom topic-specific fallback bank]
    ACCEPT -- Yes --> SYNTH[VoiceService.synthesize_question\nKokoro TTS → WAV file]
    ALT_Q --> SYNTH
    SYNTH --> CANDIDATE_ANSWER
```

### Topic Depth Ladder System

Each topic follows a 5-level depth ladder. PANELIQ tracks the current depth level per topic and always pushes to the next level:

| Level | Projects | Academics | Internships | Leadership | Career Goals |
|-------|----------|-----------|-------------|------------|--------------|
| 1 | Problem | Conceptual foundation | Role scope | Situation | Target role |
| 2 | Architecture | Application | Ownership | People challenge | Reasoning |
| 3 | Technical decisions | Edge cases | Decisions | Decision | Skills gap |
| 4 | Tradeoffs | Tradeoffs | Stakeholder tradeoffs | Conflict or tradeoff | Market understanding |
| 5 | Business impact | Business relevance | Measured impact | Learning | Long-term coherence |

### Panelist Roles & Specializations

| Panelist | Name | Triggers | Topics Owned |
|----------|------|----------|-------------|
| **Academic** (Dr. Meera Rao) | Always opens the interview | Academics, Projects, Internships, Skills |
| **Pressure** (Prof. Arvind Menon) | Contradiction detected, vague claims, short answers | Strengths, Weaknesses, Current Affairs, Contradictions |
| **MBA** (Ananya Sen) | Underrepresented, career signal, leadership gaps | Career Goals, MBA Motivation, Leadership |

---

## 📊 Full Retrieval-to-Report AI Workflow

```mermaid
flowchart LR
    subgraph INGEST["1 — Resume Ingestion"]
        PDF["PDF Upload\n(PyMuPDF)"]
        RAW["Extracted Text"]
        GROQ_PROFILE["Groq: Extract Profile\n• Education\n• Projects\n• Internships\n• Achievements\n• Skills\n• Career Goals\n• Notable Claims"]
        PDF --> RAW --> GROQ_PROFILE
    end

    subgraph SESSION["2 — Session Bootstrap"]
        PROFILE_DB["Save CandidateProfile\n→ Supabase"]
        MEM_INIT["Init InterviewMemory\n• Claims from resume\n• All topics OPEN"]
        GROQ_PROFILE --> PROFILE_DB --> MEM_INIT
    end

    subgraph LOOP["3 — Interview Loop (per turn)"]
        direction TB
        CANDIDATE_INPUT["Candidate Audio"]
        STT["Faster-Whisper STT\n→ Transcript text"]
        MEM_UPDATE["Groq: Update Memory\n• Topics covered\n• New claims\n• Contradictions\n• Follow-up opportunities\n• Panelist observations"]
        SPEAKER["Groq: Select Speaker\n(memory signals → panelist)"]
        QUESTION["Groq: Generate Question\n(topic, depth, panelist role)"]
        TTS["Kokoro TTS\n→ WAV file"]
        SAVE_MEM["Save memory\n→ Supabase (interview_memory)"]

        CANDIDATE_INPUT --> STT --> MEM_UPDATE --> SPEAKER --> QUESTION --> TTS
        QUESTION --> SAVE_MEM
    end

    subgraph REPORT_GEN["4 — Report Generation"]
        COLLECT["Collect full InterviewMemory\nfrom Supabase"]
        GROQ_REPORT["Groq: Generate Report\n• Overall score (0–10)\n• Verdict\n• Executive summary\n• Strengths & Weaknesses\n• 6 dimension scores\n• Transcript evidence\n• IIM benchmark bands\n• MBA readiness assessment\n• Panel comments"]
        COACHING["Groq: Generate Coaching Plan\n• Per-weakness follow-up question\n• Ideal answer framework\n• Why panel would ask it\n• Improvement advice"]
        PROGRESS["Analyze Progress\n• Dim-score deltas vs. prior sessions\n• Recurring weaknesses\n• Growth summary"]
        SAVE_REPORT["Save to Supabase\n• reports\n• report_scores\n• report_evidence\n• followup_questions\n• coaching_plans\n• progress_snapshots"]

        COLLECT --> GROQ_REPORT --> COACHING --> PROGRESS --> SAVE_REPORT
    end

    INGEST --> SESSION --> LOOP --> REPORT_GEN
```

---

## 🔄 How Past Reports Are Compared

PANELIQ's `/reports/compare` endpoint performs a structured delta analysis between any two completed sessions:

```mermaid
flowchart TD
    SELECT["User selects Session A and Session B"]
    LOAD_L["Load Report A\n(left) from Supabase"]
    LOAD_R["Load Report B\n(right) from Supabase"]

    SCORE_DELTA["Compute Overall Score Delta\nA.overall_score → B.overall_score\n(e.g. 5.8 → 7.1 = +1.3)"]

    DIM_DELTA["Per-Dimension Delta\nFor each of 5 dimensions:\n• Communication clarity\n• Leadership potential\n• Business awareness\n• Academic depth\n• Career clarity\nFlag as improved (≥+0.5) or regression (≤-0.5)"]

    WEAKNESS_PERSIST["Persist Weaknesses\nMatch B.weaknesses against A.weaknesses\n(normalised token overlap)\n→ remaining_weaknesses list"]

    BENCH_GAP["IIM Benchmark Gap Analysis\nFor 3 reference profiles:\n• Average CAT Aspirant (5.0–6.2 range)\n• Typical IIM Convert (6.5–7.5 range)\n• Strong IIM ABC (7.8–9.0 range)\n\nFor each dimension in Report B:\ngap = B_score − profile_mid_range\nstatus = above / within / below"]

    PANEL_OBS["Panel Observations\nTop panel comments + panel concerns\nfrom Report B"]

    RESULT["ReportComparisonResponse\n• score_changes[]\n• improved_areas[]\n• remaining_weaknesses[]\n• regressions[]\n• panel_observations[]\n• benchmark_gaps[]"]

    SELECT --> LOAD_L & LOAD_R
    LOAD_L & LOAD_R --> SCORE_DELTA --> DIM_DELTA --> WEAKNESS_PERSIST --> BENCH_GAP --> PANEL_OBS --> RESULT
```

---

## 🗄 Database Schema (DBMS Diagram)

```mermaid
erDiagram
    USERS {
        uuid id PK
        text email
        text full_name
        text avatar_url
        text provider
        timestamptz created_at
        timestamptz updated_at
    }

    USER_PROFILES {
        uuid id PK
        uuid user_id FK
        text display_name
        text background
        text goals
        boolean onboarding_completed
        timestamptz created_at
        timestamptz updated_at
    }

    RESUMES {
        uuid id PK
        uuid user_id FK
        text filename
        text content_type
        text storage_path
        text extracted_text
        text text_hash
        int version
        boolean is_active
        timestamptz parsed_at
        timestamptz deleted_at
        timestamptz created_at
    }

    CANDIDATE_PROFILES {
        uuid id PK
        uuid user_id FK
        uuid resume_id FK
        jsonb profile
        timestamptz created_at
        timestamptz updated_at
    }

    INTERVIEW_SESSIONS {
        uuid id PK
        uuid user_id FK
        uuid resume_id FK
        uuid candidate_profile_id FK
        text status
        text interview_type
        text mode
        text active_interviewer_id
        text last_speaker_reason
        int turn_count
        timestamptz started_at
        timestamptz completed_at
        int duration_seconds
        timestamptz created_at
        timestamptz updated_at
    }

    INTERVIEW_TURNS {
        uuid id PK
        uuid session_id FK
        uuid user_id FK
        int turn_index
        text speaker
        text interviewer_id
        text text
        text audio_url
        timestamptz created_at
    }

    INTERVIEW_MEMORY {
        uuid id PK
        uuid session_id FK
        uuid user_id FK
        jsonb memory
        jsonb strengths
        jsonb weaknesses
        jsonb contradictions
        jsonb speaker_history
        jsonb topic_coverage
        timestamptz created_at
        timestamptz updated_at
    }

    REPORTS {
        uuid id PK
        uuid session_id FK
        uuid user_id FK
        numeric overall_score
        text verdict
        text executive_summary
        jsonb strengths
        jsonb weaknesses
        jsonb panel_concerns
        text mba_readiness_assessment
        jsonb benchmark
        jsonb report
        timestamptz created_at
    }

    REPORT_SCORES {
        uuid id PK
        uuid report_id FK
        uuid user_id FK
        text dimension
        numeric score
        text evidence
        text advice
        jsonb strengths
        jsonb weaknesses
    }

    REPORT_EVIDENCE {
        uuid id PK
        uuid report_id FK
        uuid user_id FK
        text topic
        text evidence
        text panel_interpretation
    }

    FOLLOWUP_QUESTIONS {
        uuid id PK
        uuid report_id FK
        uuid user_id FK
        text weakness
        text question
        text why_panel_would_ask
        jsonb skills_evaluated
        text improvement_advice
        int practiced_count
        timestamptz last_practiced_at
        timestamptz created_at
    }

    IDEAL_ANSWERS {
        uuid id PK
        uuid followup_question_id FK
        uuid user_id FK
        text answer
        timestamptz created_at
    }

    COACHING_PLANS {
        uuid id PK
        uuid report_id FK
        uuid user_id FK
        jsonb plan
        timestamptz created_at
    }

    PROGRESS_SNAPSHOTS {
        uuid id PK
        uuid user_id FK
        uuid report_id FK
        numeric communication
        numeric leadership
        numeric business_awareness
        numeric mba_fit
        numeric career_clarity
        numeric academic_depth
        jsonb improved_areas
        jsonb declining_areas
        jsonb recurring_weaknesses
        text growth_summary
        jsonb next_focus_areas
        timestamptz created_at
    }

    SPEAKER_DECISIONS {
        uuid id PK
        uuid session_id FK
        uuid user_id FK
        text interviewer_id
        text reason
        text topic
        timestamptz created_at
    }

    TOPIC_TRACKING {
        uuid id PK
        uuid session_id FK
        uuid user_id FK
        text topic_name
        int depth_level
        jsonb questions_asked
        jsonb evidence_collected
        text status
        timestamptz updated_at
    }

    USERS ||--o{ USER_PROFILES : "has"
    USERS ||--o{ RESUMES : "owns"
    USERS ||--o{ CANDIDATE_PROFILES : "has"
    USERS ||--o{ INTERVIEW_SESSIONS : "runs"
    USERS ||--o{ REPORTS : "receives"
    USERS ||--o{ PROGRESS_SNAPSHOTS : "tracks"

    RESUMES ||--o{ CANDIDATE_PROFILES : "parsed into"
    CANDIDATE_PROFILES ||--o{ INTERVIEW_SESSIONS : "used in"
    RESUMES ||--o{ INTERVIEW_SESSIONS : "linked to"

    INTERVIEW_SESSIONS ||--|| INTERVIEW_MEMORY : "has one"
    INTERVIEW_SESSIONS ||--o{ INTERVIEW_TURNS : "contains"
    INTERVIEW_SESSIONS ||--|| REPORTS : "generates"
    INTERVIEW_SESSIONS ||--o{ SPEAKER_DECISIONS : "logs"
    INTERVIEW_SESSIONS ||--o{ TOPIC_TRACKING : "tracks"

    REPORTS ||--o{ REPORT_SCORES : "has"
    REPORTS ||--o{ REPORT_EVIDENCE : "has"
    REPORTS ||--o{ FOLLOWUP_QUESTIONS : "has"
    REPORTS ||--o{ COACHING_PLANS : "has"
    REPORTS ||--o{ PROGRESS_SNAPSHOTS : "snapshot"

    FOLLOWUP_QUESTIONS ||--o{ IDEAL_ANSWERS : "has"
```

---

## 🔌 REST API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service health + Supabase status |
| `GET` | `/interviewers` | List all 3 panelists |
| `GET` | `/me` | Authenticated user profile + active resume |
| `GET` | `/resume` | Get active resume record |
| `POST` | `/resume/upload` | Upload PDF, extract text, parse profile |
| `DELETE` | `/resume` | Delete active resume |
| `POST` | `/speech/transcribe` | Transcribe audio blob → text (Whisper) |
| `POST` | `/sessions` | Create new interview session |
| `POST` | `/sessions/{id}/start` | Start session, generate opening question |
| `POST` | `/sessions/{id}/turn` | Submit candidate answer, receive next question |
| `GET` | `/sessions/{id}/report` | Get evaluation report (JSON) |
| `GET` | `/sessions/{id}/report.pdf` | Download evaluation report (PDF) |
| `POST` | `/sessions/{id}/end` | End session early, trigger report generation |
| `DELETE` | `/sessions/{id}` | Delete incomplete session |
| `GET` | `/history` | All past interview sessions |
| `GET` | `/progress` | Dimension progress dashboard across sessions |
| `GET` | `/reports/compare?left_session_id=&right_session_id=` | Compare two reports with benchmark gap analysis |
| `POST` | `/practice/{practice_id}` | Mark a follow-up question as practiced |

---

## ⚙️ Local Development Setup

### Prerequisites

- Python 3.12+
- Node.js 20+
- A [Supabase](https://supabase.com/) project (with schema applied)
- A [Groq](https://groq.com/) API key

### 1. Clone & Configure Environment

```bash
git clone <repo-url>
cd paneliq
```

Create `.env` in the project root:

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_ANON_KEY=your-anon-key

# Groq
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile

# Voice (optional — browser TTS is used as fallback)
WHISPER_MODEL=base.en
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
KOKORO_LANG=a
KOKORO_VOICE_ACADEMIC=af_sarah
KOKORO_VOICE_PRESSURE=am_adam
KOKORO_VOICE_MBA=af_nicole
```

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API available at `http://localhost:8000`  
Interactive docs at `http://localhost:8000/docs`

### 3. Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
NEXT_PUBLIC_API_URL=http://localhost:8000
```

```bash
npm run dev
```

App available at `http://localhost:3000`

### 4. Database

Apply the schema to your Supabase project:

```bash
# Via Supabase CLI
supabase db push

# Or paste supabase/schema.sql directly into the Supabase SQL editor
```

To seed the demo account:

```bash
# In Supabase SQL editor
\i supabase/seed_demo_account.sql
```

---

## 🧠 Intelligence Module Map

| Function | What it does |
|----------|-------------|
| `create_candidate_profile()` | Groq extracts structured profile from raw resume text |
| `generate_opening_question()` | Always starts with the Academic panelist on the strongest resume item |
| `update_memory()` | Groq updates shared memory: topics, claims, weaknesses, contradictions, follow-ups |
| `select_speaker()` | Groq (or local fallback) picks next panelist based on memory signals |
| `generate_question()` | Groq generates one question for the selected panelist at the correct depth level |
| `_finalize_question()` | Validates question: no duplicates, no verbatim candidate speech, no filler |
| `generate_report()` | Groq synthesizes full evaluation report from complete transcript + memory |
| `generate_coaching_items()` | Groq generates per-weakness coaching cards with ideal answer frameworks |
| `analyze_progress()` | Delta analysis across all user reports — identifies trends and recurring issues |
| `compare_reports()` | Side-by-side dimension delta + IIM benchmark gap computation |
| `_force_silent_panelist()` | Hard rule: ensures all 3 panelists speak within the first 3 turns |

---

## 📋 Interview Completion Criteria

The interview ends when **any** of these conditions is met:

1. **Turn count ≥ 12** — full interview round completed
2. **Wall-clock ≥ 25 minutes** — time limit reached
3. **Sufficient depth** — all of these hold simultaneously:
   - ≥ 4 candidate turns
   - ≥ 4 distinct topics covered
   - ≥ 2 substantive answers (≥ 40 words each)
   - All 3 panelists have spoken at least once
4. **Candidate explicitly requests to end** (e.g., "I want to end", "wrap up")

---

## 📄 Report Structure

Each generated report contains:

| Section | Content |
|---------|---------|
| **Verdict** | Likely Convert / Borderline / Needs Improvement |
| **Overall Score** | 0–10 composite |
| **Executive Summary** | Narrative assessment anchored in transcript evidence |
| **Strengths** | Evidence-backed strengths list |
| **Weaknesses** | Evidence-backed weaknesses list |
| **Dimensions** | 6 dimension scores with evidence, advice, and per-dimension strengths/weaknesses |
| **Transcript Evidence** | Topic-wise quotes with panel interpretations |
| **IIM Benchmarks** | Score bands for 3 reference profiles across 5 dimensions |
| **MBA Readiness Assessment** | Narrative MBA fit evaluation |
| **Panel Comments** | Panel-level notes per topic coverage |
| **Coaching Plan** | Per-weakness: follow-up question, ideal answer, skills evaluated, practice advice |
| **Progress Analysis** | Cross-session delta summary (if ≥ 2 interviews completed) |

---

## 🔐 Security

- All API endpoints require a valid Supabase JWT (`Authorization: Bearer <token>`)
- Row-level security is enforced: users can only access their own sessions, reports, and resumes
- Service role key is backend-only and never exposed to the frontend
- Resume text is stored server-side; the extracted text is only served to the authenticated user who uploaded it

---

## 📜 License

MIT — see [LICENSE](LICENSE) for details.

---

<div align="center">
Built with ❤️ for serious MBA aspirants preparing for IIM, ISB, and top B-school interviews.
</div>
