from pathlib import Path
import asyncio
import logging
import os
import textwrap
from contextlib import asynccontextmanager

# Load .env from repo root (two levels up from this file) before anything else.
# This ensures SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY etc. are available
# regardless of how uvicorn is launched (direct, PM2, IDE run config, etc.).
from dotenv import load_dotenv as _load_dotenv
_load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

import fitz
from fastapi import Depends, File, Form, Header, HTTPException, Response, UploadFile
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

from app.database import SupabaseRepository
from app.interviewers import INTERVIEWERS
from app.models import (
    AuthenticatedUser,
    BenchmarkGapDimension,
    BenchmarkGapProfile,
    CandidateTurnRequest,
    CreateSessionRequest,
    EndSessionResponse,
    InterviewHistoryItem,
    InterviewReport,
    InterviewStatus,
    InterviewTurnResponse,
    PracticeAgainResponse,
    ProgressDashboardResponse,
    ReportComparisonResponse,
    ResumeDeleteResponse,
    ResumeRecord,
    ResumeUploadResponse,
    SessionResponse,
    TranscriptionResponse,
    UserProfileResponse,
)
from app.orchestrator import InterviewOrchestrator
from app.resume import ResumeProcessingError, extract_resume_text
from app.voice import VoiceProcessingError, VoiceService


audio_dir = Path(__file__).resolve().parents[1] / "generated_audio"
voice_service = VoiceService(audio_dir=audio_dir)
repository = SupabaseRepository()
orchestrator = InterviewOrchestrator(voice_service=voice_service, repository=repository)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate Supabase connectivity at startup; clean up audio on shutdown."""
    if repository.is_configured:
        try:
            client = repository.require()
            client.table("users").select("id").limit(1).execute()
            logger.info("\u2705 Supabase connectivity: OK")
        except Exception as exc:  # noqa: BLE001
            # Log but do NOT crash — allows degraded mode where /health/deep
            # can still diagnose the issue after deploy.
            logger.warning("\u26a0\ufe0f  Supabase connectivity check failed: %s", exc)
    else:
        logger.warning(
            "\u26a0\ufe0f  Supabase is NOT configured — set SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY in Render environment variables."
        )
    yield  # application runs here
    # Shutdown: remove all generated audio files so the ephemeral Render
    # filesystem doesn't accumulate WAV files across graceful restarts.
    n = voice_service.cleanup_all_audio()
    if n:
        logger.info("\U0001f9f9 Cleaned up %d audio file(s) on shutdown.", n)


app = FastAPI(title="PANELIQ API", version="0.1.0", lifespan=lifespan)
app.mount("/audio", StaticFiles(directory=audio_dir), name="audio")

_cors_origins_raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Fast health check — no live DB call. Use /health/deep to verify DB."""
    import h11
    groq_status = "configured" if os.getenv("GROQ_API_KEY") else "missing"
    return {
        "status": "ok",
        "supabase": "configured" if repository.is_configured else "missing",
        "groq": groq_status,
        "cors_origins": os.getenv("ALLOWED_ORIGINS", "localhost-only"),
        # Deployment verification: confirm transport pins are active.
        "h11_version": h11.__version__,
        "http2": "disabled",
    }


@app.get("/health/deep")
def health_deep() -> dict[str, object]:
    """Deep health check: verifies live Supabase DB connectivity and Groq key presence."""
    results: dict[str, object] = {"status": "ok"}

    # Test Supabase DB round-trip
    try:
        client = repository.require()
        client.table("users").select("id").limit(1).execute()
        results["supabase_db"] = "connected"
    except Exception as exc:
        results["supabase_db"] = f"error: {str(exc)[:120]}"
        results["status"] = "degraded"

    # Verify Groq key is present (don't make a live API call to avoid charges)
    results["groq_api_key"] = "set" if os.getenv("GROQ_API_KEY") else "missing"
    if not os.getenv("GROQ_API_KEY"):
        results["status"] = "degraded"

    results["allowed_origins"] = os.getenv("ALLOWED_ORIGINS", "localhost-only (set ALLOWED_ORIGINS in production)")
    return results



def current_user(
    authorization: str | None = Header(default=None),
) -> AuthenticatedUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sign in with Supabase Auth.")
    user_data = repository.verify_access_token(authorization.split(" ", 1)[1])
    repository.ensure_user(user_data)
    return AuthenticatedUser(**user_data)


@app.get("/interviewers")
def get_interviewers():
    return INTERVIEWERS


@app.get("/me", response_model=UserProfileResponse)
async def get_me(user: AuthenticatedUser = Depends(current_user)) -> UserProfileResponse:
    loop = asyncio.get_running_loop()
    resume = await loop.run_in_executor(None, repository.get_active_resume, user.id)
    _, profile = await loop.run_in_executor(None, repository.latest_candidate_profile, user.id)
    return UserProfileResponse(
        user=user,
        profile=profile.model_dump(mode="json") if profile else None,
        resume=resume,
    )


@app.get("/resume", response_model=ResumeRecord | None)
async def get_resume(user: AuthenticatedUser = Depends(current_user)) -> ResumeRecord | None:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, repository.get_active_resume, user.id)


@app.post("/resume/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    name: str = Form("Candidate"),
    goals: str = Form(""),
    background: str = Form(""),
    user: AuthenticatedUser = Depends(current_user),
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
        repository.update_user_profile(
            user_id=user.id,
            display_name=profile.name or name,
            background=background,
            goals=goals,
        )
        resume = repository.create_resume(
            user_id=user.id,
            filename=file.filename or "resume",
            content_type=file.content_type,
            extracted_text=extracted_text,
            profile=profile,
        )
        return ResumeUploadResponse(
            resume_id=resume.id,
            filename=file.filename or "resume",
            extracted_text=extracted_text,
            profile=profile,
            version=resume.version,
            parsed_at=resume.parsed_at,
        )
    except ResumeProcessingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.delete("/resume", response_model=ResumeDeleteResponse)
async def delete_resume(user: AuthenticatedUser = Depends(current_user)) -> ResumeDeleteResponse:
    loop = asyncio.get_running_loop()
    deleted = await loop.run_in_executor(None, repository.delete_active_resume, user.id)
    return ResumeDeleteResponse(deleted=deleted)


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
async def create_session(
    request: CreateSessionRequest,
    user: AuthenticatedUser = Depends(current_user),
) -> SessionResponse:
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, orchestrator.create_session, user.id, request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/sessions/{session_id}/start", response_model=InterviewTurnResponse)
async def start_session(
    session_id: str,
    user: AuthenticatedUser = Depends(current_user),
) -> InterviewTurnResponse:
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, orchestrator.start_session, user.id, session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None


@app.post("/sessions/{session_id}/turn", response_model=InterviewTurnResponse)
async def add_turn(
    session_id: str,
    request: CandidateTurnRequest,
    user: AuthenticatedUser = Depends(current_user),
) -> InterviewTurnResponse:
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(
            None, orchestrator.add_candidate_turn, user.id, session_id, request
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None


@app.get("/sessions/{session_id}/report", response_model=InterviewReport)
async def get_report(
    session_id: str,
    user: AuthenticatedUser = Depends(current_user),
) -> InterviewReport:
    loop = asyncio.get_running_loop()
    stored_report = await loop.run_in_executor(None, repository.get_report, user.id, session_id)
    if stored_report:
        return stored_report
    try:
        return await loop.run_in_executor(None, orchestrator.generate_report, user.id, session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None


@app.get("/sessions/{session_id}/report.pdf")
async def get_report_pdf(
    session_id: str,
    user: AuthenticatedUser = Depends(current_user),
) -> Response:
    loop = asyncio.get_running_loop()
    try:
        report = await loop.run_in_executor(
            None, repository.get_report, user.id, session_id
        ) or await loop.run_in_executor(None, orchestrator.generate_report, user.id, session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    pdf_bytes = await loop.run_in_executor(None, _render_report_pdf, report)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="paneliq-report-{session_id}.pdf"'},
    )


@app.post("/sessions/{session_id}/end", response_model=EndSessionResponse)
async def end_session(
    session_id: str,
    user: AuthenticatedUser = Depends(current_user),
) -> EndSessionResponse:
    loop = asyncio.get_running_loop()
    try:
        report = await loop.run_in_executor(None, orchestrator.end_session, user.id, session_id)
        return EndSessionResponse(
            session_id=session_id,
            status=InterviewStatus.completed,
            report=report,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None


@app.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: AuthenticatedUser = Depends(current_user),
) -> dict:
    loop = asyncio.get_running_loop()
    deleted = await loop.run_in_executor(
        None, repository.delete_incomplete_session, user.id, session_id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found or already completed")
    return {"deleted": True, "session_id": session_id}


@app.get("/history", response_model=list[InterviewHistoryItem])
async def get_history(user: AuthenticatedUser = Depends(current_user)) -> list[InterviewHistoryItem]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, repository.history, user.id)


@app.get("/progress", response_model=ProgressDashboardResponse)
async def get_progress(user: AuthenticatedUser = Depends(current_user)) -> ProgressDashboardResponse:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, repository.progress_dashboard, user.id)


@app.get("/reports/compare", response_model=ReportComparisonResponse)
async def compare_reports(
    left_session_id: str,
    right_session_id: str,
    user: AuthenticatedUser = Depends(current_user),
) -> ReportComparisonResponse:
    loop = asyncio.get_running_loop()
    left = await loop.run_in_executor(None, repository.get_report, user.id, left_session_id)
    right = await loop.run_in_executor(None, repository.get_report, user.id, right_session_id)
    if not left or not right:
        raise HTTPException(status_code=404, detail="Report not found")
    comparison = await loop.run_in_executor(None, orchestrator.compare_reports, left, right)
    return ReportComparisonResponse(left=left, right=right, **comparison)


@app.post("/practice/{practice_id}", response_model=PracticeAgainResponse)
def practice_again(
    practice_id: str,
    user: AuthenticatedUser = Depends(current_user),
) -> PracticeAgainResponse:
    try:
        count, question = repository.mark_practiced(user.id, practice_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Practice question not found") from None
    return PracticeAgainResponse(practice_id=practice_id, practiced_count=count, question=question)


def _render_report_pdf(report: InterviewReport) -> bytes:
    document = fitz.open()
    page = document.new_page()
    y = 54
    left = 54
    width = 500

    def write_line(text: str, size: int = 10, bold: bool = False) -> None:
        nonlocal page, y
        font = "helv"
        if y > 760:
            page = document.new_page()
            y = 54
        page.insert_text((left, y), text, fontsize=size, fontname=font)
        if bold:
            page.draw_line((left, y + 3), (min(left + width, left + len(text) * size * 0.48), y + 3))
        y += size + 7

    def write_wrapped(text: str, size: int = 10) -> None:
        for line in textwrap.wrap(text, width=92):
            write_line(line, size=size)

    def section(title: str) -> None:
        nonlocal y
        y += 8
        write_line(title, size=13, bold=True)

    write_line("PANELIQ Interview Evaluation Report", size=16, bold=True)
    write_line(f"Verdict: {report.verdict} | Overall score: {report.overall_score}/10", size=11)
    write_wrapped(report.benchmark_disclaimer, size=9)

    section("Executive Summary")
    write_wrapped(report.executive_summary or report.feedback_to_candidate)

    section("Strengths")
    for item in report.strengths or ["Insufficient transcript evidence."]:
        write_wrapped(f"- {item}")

    section("Weaknesses")
    for item in report.weaknesses or ["Insufficient transcript evidence."]:
        write_wrapped(f"- {item}")

    section("Transcript Evidence")
    for item in report.transcript_evidence:
        write_wrapped(f"- {item.topic}: {item.evidence} Panel view: {item.panel_interpretation}")

    section("Recommended Improvements")
    for item in report.recommended_improvements:
        write_wrapped(f"- {item}")

    section("MBA Readiness Assessment")
    write_wrapped(report.mba_readiness_assessment or "Insufficient evidence.")

    section("Coaching Section")
    for item in report.coaching_items:
        write_wrapped(f"- Weakness: {item.weakness}")
        write_wrapped(f"  Follow-up: {item.question}")
        write_wrapped(f"  Why panel asks: {item.why_panel_would_ask}")
        write_wrapped(f"  Ideal answer: {item.ideal_answer}")
        write_wrapped(f"  Advice: {item.improvement_advice}")

    if report.progress:
        section("Progress Section")
        write_wrapped(report.progress.growth_summary)
        for item in report.progress.next_focus_areas:
            write_wrapped(f"- Focus: {item}")

    section("Panel Comments")
    for item in report.panel_comments:
        write_wrapped(f"- {item}")

    section("Benchmarking")
    for item in report.benchmarking:
        write_wrapped(
            f"- {item.category}: Communication {item.communication}; Leadership {item.leadership}; "
            f"Business Awareness {item.business_awareness}; Academic Depth {item.academic_depth}; "
            f"MBA Fit {item.mba_fit}. {item.notes}"
        )

    data = document.tobytes()
    document.close()
    return data
