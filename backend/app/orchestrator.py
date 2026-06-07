from datetime import datetime, timedelta
from uuid import uuid4

from app.database import SupabaseRepository
from app.intelligence import InterviewIntelligence
from app.interviewers import INTERVIEWERS
from app.models import (
    CandidateClaim,
    CandidateProfile,
    CandidateTurnRequest,
    CreateSessionRequest,
    InterviewMemory,
    InterviewStatus,
    InterviewTurnResponse,
    InterviewerId,
    InterviewReport,
    SessionResponse,
    TranscriptTurn,
    TurnSpeaker,
)
from app.voice import VoiceService


MAX_DURATION_SECONDS = 1500  # 25-minute interview wall-clock limit


class InterviewOrchestrator:
    """Production orchestrator backed by Supabase interview memory."""

    def __init__(
        self,
        voice_service: VoiceService | None = None,
        repository: SupabaseRepository | None = None,
    ) -> None:
        self._repository = repository or SupabaseRepository()
        self._intelligence = InterviewIntelligence()
        self._voice_service = voice_service

    def create_candidate_profile(self, request: CreateSessionRequest) -> CandidateProfile:
        return self._intelligence.create_candidate_profile(request)

    def create_session(self, user_id: str, request: CreateSessionRequest) -> SessionResponse:
        session_id = str(uuid4())
        resume_id = request.resume_id
        candidate_profile_id = None
        if request.resume_text.strip():
            profile = self._intelligence.create_candidate_profile(request)
            candidate_profile_id = self._repository.save_candidate_profile(user_id, resume_id, profile)
        else:
            active_resume = self._repository.get_active_resume(user_id)
            resume_id = request.resume_id or (active_resume.id if active_resume else None)
            if resume_id:
                candidate_profile_id, profile = self._repository.candidate_profile_for_resume(
                    user_id, resume_id
                )
            else:
                candidate_profile_id, profile = self._repository.latest_candidate_profile(user_id)
            if not profile:
                raise ValueError("Upload a resume before creating the first interview.")
        memory = InterviewMemory(session_id=session_id, candidate=profile)
        for claim in profile.notable_resume_claims:
            memory.candidate_claims.append(
                CandidateClaim(text=claim, source="resume", evidence=claim)
            )
        self._repository.create_session(
            user_id=user_id,
            memory=memory,
            resume_id=resume_id,
            candidate_profile_id=candidate_profile_id,
            interview_type=request.interview_type,
        )

        return SessionResponse(
            session_id=session_id,
            status=memory.status,
            candidate=profile,
            interviewers=INTERVIEWERS,
            max_duration_seconds=MAX_DURATION_SECONDS,
        )

    def get_session(self, user_id: str, session_id: str) -> InterviewMemory:
        return self._repository.load_memory(user_id, session_id)

    def start_session(self, user_id: str, session_id: str) -> InterviewTurnResponse:
        memory = self.get_session(user_id, session_id)
        if memory.transcript:
            return self._turn_response(memory, memory.transcript[-1].text)
        memory.status = InterviewStatus.in_progress
        memory.active_interviewer_id = InterviewerId.academic
        memory.speaker_history.append(InterviewerId.academic)
        memory.last_speaker_reason = "Begin with resume-grounded academic/profile validation."
        self._repository.record_speaker_decision(
            user_id,
            session_id,
            InterviewerId.academic.value,
            memory.last_speaker_reason,
            "opening",
        )

        question = self._intelligence.generate_opening_question(memory)
        memory.transcript.append(
            TranscriptTurn(
                speaker=TurnSpeaker.interviewer,
                interviewer_id=InterviewerId.academic,
                text=question,
            )
        )
        self._repository.save_memory(user_id, memory)

        return self._turn_response(memory, question)

    def add_candidate_turn(
        self, user_id: str, session_id: str, request: CandidateTurnRequest
    ) -> InterviewTurnResponse:
        memory = self.get_session(user_id, session_id)
        if memory.status == InterviewStatus.completed:
            return self._turn_response(
                memory,
                "The interview has already ended. Please review your report.",
            )

        answer = request.transcript.strip()
        memory.transcript.append(
            TranscriptTurn(speaker=TurnSpeaker.candidate, text=answer)
        )
        memory.turn_count += 1
        self._intelligence.update_memory(memory, answer)

        # ── Early-exit: candidate explicitly wants to stop ──────────
        if _candidate_wants_to_end(answer):
            memory.status = InterviewStatus.completed
            memory.completed_at = datetime.utcnow()
            memory.active_interviewer_id = InterviewerId.mba
            memory.speaker_history.append(InterviewerId.mba)
            memory.last_speaker_reason = "Candidate indicated they want to end the session."
            closing = (
                "Understood — we will wrap up here. "
                "The panel has noted your responses and will now prepare your evaluation report. "
                "Please review your score and coaching feedback below."
            )
            memory.transcript.append(
                TranscriptTurn(
                    speaker=TurnSpeaker.interviewer,
                    interviewer_id=InterviewerId.mba,
                    text=closing,
                )
            )
            self._repository.save_memory(user_id, memory)
            return self._turn_response(memory, closing)

        # ── Check wall-clock limit ──────────────────────────────────
        elapsed = (datetime.utcnow() - memory.started_at).total_seconds()
        time_is_up = elapsed >= MAX_DURATION_SECONDS

        # ── Smart completion: enough substance even if under hard cap ─
        sufficient = _transcript_is_sufficient(memory)

        if memory.turn_count >= 12 or time_is_up or sufficient:
            memory.status = InterviewStatus.completed
            memory.completed_at = datetime.utcnow()
            memory.active_interviewer_id = InterviewerId.mba
            memory.speaker_history.append(InterviewerId.mba)
            if time_is_up and not sufficient:
                memory.last_speaker_reason = "Interview time limit reached — closing the panel session."
                closing = (
                    "Thank you — our time is up for this round. "
                    "The panel will now prepare your evaluation report. "
                    "Please review your score and coaching feedback below."
                )
            elif sufficient and memory.turn_count < 12:
                memory.last_speaker_reason = "Transcript contains sufficient evidence — closing early."
                closing = (
                    "The panel has gathered enough depth to evaluate you properly. "
                    "We will close here and prepare your detailed report. "
                    "Well done — please review your score below."
                )
            else:
                memory.last_speaker_reason = "Interview completed after full round of questions."
                closing = (
                    "Thank you — that completes this panel round. "
                    "You may review your evaluation report below."
                )
            memory.transcript.append(
                TranscriptTurn(
                    speaker=TurnSpeaker.interviewer,
                    interviewer_id=InterviewerId.mba,
                    text=closing,
                )
            )
            self._repository.save_memory(user_id, memory)
            return self._turn_response(memory, closing)

        selection = self._intelligence.select_speaker(memory)
        memory.active_interviewer_id = selection.speaker
        memory.speaker_history.append(selection.speaker)
        self._repository.record_speaker_decision(
            user_id,
            session_id,
            selection.speaker.value,
            selection.reason,
            selection.topic,
        )
        question = self._intelligence.generate_question(
            memory=memory,
            interviewer_id=selection.speaker,
            latest_answer=answer,
            selection_reason=selection.reason,
            selected_topic=selection.topic,
        )
        memory.transcript.append(
            TranscriptTurn(
                speaker=TurnSpeaker.interviewer,
                interviewer_id=selection.speaker,
                text=question,
            )
        )
        self._repository.save_memory(user_id, memory)
        return self._turn_response(memory, question)

    def generate_report(self, user_id: str, session_id: str) -> InterviewReport:
        existing = self._repository.get_report(user_id, session_id)
        if existing:
            return existing
        memory = self.get_session(user_id, session_id)
        report = self._intelligence.generate_report(memory)
        reports = self._repository.list_reports(user_id) + [report]
        progress = self._intelligence.analyze_progress(reports)
        return self._repository.save_report(user_id, report, progress)

    def end_session(self, user_id: str, session_id: str) -> InterviewReport:
        memory = self.get_session(user_id, session_id)
        if memory.status != InterviewStatus.completed:
            memory.status = InterviewStatus.completed
            memory.completed_at = datetime.utcnow()
            if memory.active_interviewer_id is None:
                memory.active_interviewer_id = InterviewerId.mba
            memory.last_speaker_reason = "Candidate ended the interview and requested the panel report."
            self._repository.save_memory(user_id, memory)
        report = self._intelligence.generate_report(memory)
        reports = self._repository.list_reports(user_id) + [report]
        progress = self._intelligence.analyze_progress(reports)
        return self._repository.save_report(user_id, report, progress)

    def compare_reports(self, left: InterviewReport, right: InterviewReport) -> dict[str, list[str]]:
        return self._intelligence.compare_reports(left, right)

    def _turn_response(self, memory: InterviewMemory, subtitle: str) -> InterviewTurnResponse:
        audio_url = None
        if self._voice_service and memory.active_interviewer_id:
            audio_url = self._voice_service.synthesize_question(
                subtitle, memory.active_interviewer_id.value
            )
        return InterviewTurnResponse(
            session_id=memory.session_id,
            active_interviewer_id=memory.active_interviewer_id or InterviewerId.academic,
            speaker_reason=memory.last_speaker_reason,
            subtitle_text=subtitle,
            audio_url=audio_url,
            voice_strategy="server_audio" if audio_url else "browser_speech_synthesis",
            status=memory.status,
            transcript=memory.transcript,
        )


# ─── Module-level helpers ──────────────────────────────────────────────────────

_END_PHRASES = [
    "i want to end",
    "i want to stop",
    "end the interview",
    "stop the interview",
    "let's wrap up",
    "let us wrap up",
    "wrap up the interview",
    "i'm done",
    "i am done",
    "that's all from me",
    "that is all from me",
    "no more questions",
    "i'd like to end",
    "i would like to end",
    "please end",
    "close the interview",
    "finish the interview",
]


def _candidate_wants_to_end(answer: str) -> bool:
    """Return True when the candidate's answer signals they want to stop."""
    lower = answer.lower().strip()
    return any(phrase in lower for phrase in _END_PHRASES)


def _transcript_is_sufficient(memory: InterviewMemory) -> bool:
    """Return True when the transcript has enough evidence to produce a quality report.

    Criteria (all must hold):
    - At least 4 candidate turns
    - At least 4 distinct topics touched
    - At least 2 substantive answers (>=40 words each)
    - At least one turn from each of the three interviewers
    """
    candidate_turns = [
        t for t in memory.transcript if t.speaker == TurnSpeaker.candidate
    ]
    if len(candidate_turns) < 4:
        return False

    topics_covered = set(memory.topics_covered)
    if len(topics_covered) < 4:
        return False

    substantive = sum(1 for t in candidate_turns if len(t.text.split()) >= 40)
    if substantive < 2:
        return False

    # All three interviewers must have spoken at least once
    panelists = {t.interviewer_id for t in memory.transcript if t.speaker == TurnSpeaker.interviewer}
    if len(panelists) < 3:
        return False

    return True

