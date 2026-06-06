from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.interviewers import INTERVIEWERS
from app.models import (
    CandidateTurnRequest,
    CreateSessionRequest,
    InterviewReport,
    InterviewTurnResponse,
    ResumeUploadResponse,
    SessionResponse,
    TranscriptionResponse,
)
from app.orchestrator import InterviewOrchestrator
from app.resume import ResumeProcessingError, extract_resume_text
from app.voice import VoiceProcessingError, VoiceService


app = FastAPI(title="PANELIQ API", version="0.1.0")
audio_dir = Path(__file__).resolve().parents[1] / "generated_audio"
voice_service = VoiceService(audio_dir=audio_dir)
orchestrator = InterviewOrchestrator(voice_service=voice_service)
app.mount("/audio", StaticFiles(directory=audio_dir), name="audio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/interviewers")
def get_interviewers():
    return INTERVIEWERS


@app.post("/resume/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    name: str = Form("Candidate"),
    goals: str = Form(""),
    background: str = Form(""),
) -> ResumeUploadResponse:
    try:
        extracted_text = await extract_resume_text(file)
        profile = orchestrator.create_candidate_profile(
            CreateSessionRequest(
                name=name,
                goals=goals,
                background=background,
                resume_text=extracted_text,
            )
        )
        return ResumeUploadResponse(
            filename=file.filename or "resume",
            extracted_text=extracted_text,
            profile=profile,
        )
    except ResumeProcessingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/speech/transcribe", response_model=TranscriptionResponse)
async def transcribe_answer(file: UploadFile = File(...)) -> TranscriptionResponse:
    try:
        transcript, language, duration = await voice_service.transcribe(file)
        return TranscriptionResponse(
            transcript=transcript,
            language=language,
            duration_seconds=duration,
        )
    except VoiceProcessingError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/sessions", response_model=SessionResponse)
def create_session(request: CreateSessionRequest) -> SessionResponse:
    return orchestrator.create_session(request)


@app.post("/sessions/{session_id}/start", response_model=InterviewTurnResponse)
def start_session(session_id: str) -> InterviewTurnResponse:
    try:
        return orchestrator.start_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None


@app.post("/sessions/{session_id}/turn", response_model=InterviewTurnResponse)
def add_turn(session_id: str, request: CandidateTurnRequest) -> InterviewTurnResponse:
    try:
        return orchestrator.add_candidate_turn(session_id, request)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None


@app.get("/sessions/{session_id}/report", response_model=InterviewReport)
def get_report(session_id: str) -> InterviewReport:
    try:
        return orchestrator.generate_report(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None
