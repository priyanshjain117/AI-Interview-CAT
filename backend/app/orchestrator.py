from datetime import datetime
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
