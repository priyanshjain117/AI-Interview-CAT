from datetime import datetime
from uuid import uuid4

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


class InterviewOrchestrator:
    """In-memory MVP orchestrator backed by a shared intelligence layer."""

    def __init__(self, voice_service: VoiceService | None = None) -> None:
        self._sessions: dict[str, InterviewMemory] = {}
        self._intelligence = InterviewIntelligence()
        self._voice_service = voice_service

    def create_candidate_profile(self, request: CreateSessionRequest) -> CandidateProfile:
        return self._intelligence.create_candidate_profile(request)

    def create_session(self, request: CreateSessionRequest) -> SessionResponse:
        session_id = str(uuid4())
        profile = self._intelligence.create_candidate_profile(request)
        memory = InterviewMemory(session_id=session_id, candidate=profile)
        for claim in profile.notable_resume_claims:
            memory.candidate_claims.append(
                CandidateClaim(text=claim, source="resume", evidence=claim)
            )
        self._sessions[session_id] = memory

        return SessionResponse(
            session_id=session_id,
            status=memory.status,
            candidate=profile,
            interviewers=INTERVIEWERS,
        )

    def get_session(self, session_id: str) -> InterviewMemory:
        if session_id not in self._sessions:
            raise KeyError(session_id)
        return self._sessions[session_id]

    def start_session(self, session_id: str) -> InterviewTurnResponse:
        memory = self.get_session(session_id)
        memory.status = InterviewStatus.in_progress
        memory.active_interviewer_id = InterviewerId.academic
        memory.speaker_history.append(InterviewerId.academic)
        memory.last_speaker_reason = "Begin with resume-grounded academic/profile validation."

        question = self._intelligence.generate_opening_question(memory)
        memory.transcript.append(
            TranscriptTurn(
                speaker=TurnSpeaker.interviewer,
                interviewer_id=InterviewerId.academic,
                text=question,
            )
        )

        return self._turn_response(memory, question)

    def add_candidate_turn(
        self, session_id: str, request: CandidateTurnRequest
    ) -> InterviewTurnResponse:
        memory = self.get_session(session_id)
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

        if memory.turn_count >= 7:
            memory.status = InterviewStatus.completed
            memory.completed_at = datetime.utcnow()
            memory.active_interviewer_id = InterviewerId.mba
            memory.speaker_history.append(InterviewerId.mba)
            memory.last_speaker_reason = "Close the interview after enough turns for an MVP report."
            closing = (
                "Thank you. We have enough to evaluate this round. "
                "You may stop here and review the panel report."
            )
            memory.transcript.append(
                TranscriptTurn(
                    speaker=TurnSpeaker.interviewer,
                    interviewer_id=InterviewerId.mba,
                    text=closing,
                )
            )
            return self._turn_response(memory, closing)

        selection = self._intelligence.select_speaker(memory)
        memory.active_interviewer_id = selection.speaker
        memory.speaker_history.append(selection.speaker)
        question = self._intelligence.generate_question(
            memory=memory,
            interviewer_id=selection.speaker,
            latest_answer=answer,
            selection_reason=selection.reason,
        )
        memory.transcript.append(
            TranscriptTurn(
                speaker=TurnSpeaker.interviewer,
                interviewer_id=selection.speaker,
                text=question,
            )
        )
        return self._turn_response(memory, question)

    def generate_report(self, session_id: str) -> InterviewReport:
        memory = self.get_session(session_id)
        return self._intelligence.generate_report(memory)

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
