from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class InterviewerId(str, Enum):
    academic = "academic"
    pressure = "pressure"
    mba = "mba"


class InterviewStatus(str, Enum):
    ready = "ready"
    in_progress = "in_progress"
    completed = "completed"


class TurnSpeaker(str, Enum):
    candidate = "candidate"
    interviewer = "interviewer"


class TopicStatus(str, Enum):
    open = "OPEN"
    in_progress = "IN_PROGRESS"
    sufficiently_tested = "SUFFICIENTLY_TESTED"
    closed = "CLOSED"


class TopicState(BaseModel):
    topic_name: str
    depth_level: int = 0
    questions_asked: list[str] = Field(default_factory=list)
    evidence_collected: list[str] = Field(default_factory=list)
    status: TopicStatus = TopicStatus.open


class CandidateClaim(BaseModel):
    text: str
    source: Literal["resume", "interview"] = "interview"
    evidence: str = ""
    challenged: bool = False


class FollowUpOpportunity(BaseModel):
    topic: str
    reason: str
    suggested_interviewer: InterviewerId
    source_claim: str = ""


class InterviewerObservation(BaseModel):
    interviewer_id: InterviewerId
    note: str
    evidence: str = ""


class SpeakerSelection(BaseModel):
    speaker: InterviewerId
    reason: str
    topic: str = ""


class CandidateProfile(BaseModel):
    name: str = "Candidate"
    resume_text: str = ""
    goals: str = ""
    background: str = ""
    education: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    internships: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    career_goals: list[str] = Field(default_factory=list)
    notable_resume_claims: list[str] = Field(default_factory=list)


class TranscriptTurn(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    speaker: TurnSpeaker
    text: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    interviewer_id: InterviewerId | None = None


class InterviewerState(BaseModel):
    id: InterviewerId
    name: str
    role: str
    focus: str


class InterviewMemory(BaseModel):
    session_id: str
    candidate: CandidateProfile
    status: InterviewStatus = InterviewStatus.ready
    active_interviewer_id: InterviewerId | None = None
    transcript: list[TranscriptTurn] = Field(default_factory=list)
    topics_covered: list[str] = Field(default_factory=list)
    topic_states: list[TopicState] = Field(default_factory=list)
    asked_questions: list[str] = Field(default_factory=list)
    candidate_claims: list[CandidateClaim] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    unanswered_follow_up_opportunities: list[FollowUpOpportunity] = Field(default_factory=list)
    interviewer_observations: list[InterviewerObservation] = Field(default_factory=list)
    speaker_history: list[InterviewerId] = Field(default_factory=list)
    last_speaker_reason: str = ""
    turn_count: int = 0
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

    @property
    def claims(self) -> list[str]:
        return [claim.text for claim in self.candidate_claims]

    @property
    def concerns(self) -> list[str]:
        return self.weaknesses + self.contradictions


class CreateSessionRequest(BaseModel):
    name: str = "Candidate"
    goals: str = ""
    background: str = ""
    resume_text: str = ""
    resume_id: str | None = None
    interview_type: str = "IIM MBA Panel"

    @field_validator("resume_text")
    @classmethod
    def reject_resume_placeholders(cls, value: str) -> str:
        lower = value.lower()
        blocked_fragments = [
            "uploaded resume:",
            "pdf extraction is handled",
            "backend integration phase",
        ]
        if any(fragment in lower for fragment in blocked_fragments):
            raise ValueError("Resume text must be extracted content, not an upload placeholder.")
        return value


class SessionResponse(BaseModel):
    session_id: str
    status: InterviewStatus
    candidate: CandidateProfile
    interviewers: list[InterviewerState]


class CandidateTurnRequest(BaseModel):
    transcript: str = Field(min_length=1)


class ResumeUploadResponse(BaseModel):
    resume_id: str | None = None
    filename: str
    extracted_text: str
    profile: CandidateProfile
    version: int = 1
    parsed_at: datetime = Field(default_factory=datetime.utcnow)


class ResumeRecord(BaseModel):
    id: str
    filename: str
    extracted_text: str
    version: int
    is_active: bool
    parsed_at: datetime
    created_at: datetime


class ResumeDeleteResponse(BaseModel):
    deleted: bool


class TranscriptionResponse(BaseModel):
    transcript: str
    language: str | None = None
    duration_seconds: float | None = None


class InterviewTurnResponse(BaseModel):
    session_id: str
    active_interviewer_id: InterviewerId
    speaker_reason: str = ""
    subtitle_text: str
    audio_url: str | None = None
    voice_strategy: Literal["browser_speech_synthesis", "server_audio"] = "browser_speech_synthesis"
    status: InterviewStatus
    transcript: list[TranscriptTurn]


class DimensionScore(BaseModel):
    name: str
    score: float | None
    evidence: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    advice: str


class TranscriptEvidence(BaseModel):
    topic: str
    evidence: str
    panel_interpretation: str


class BenchmarkCategory(BaseModel):
    category: Literal[
        "Typical IIM Convert Candidate",
        "Strong IIM ABC Candidate",
        "Average CAT Aspirant",
    ]
    communication: str
    leadership: str
    business_awareness: str
    academic_depth: str
    mba_fit: str
    notes: str


class FollowUpCoachingItem(BaseModel):
    weakness: str
    question: str
    why_panel_would_ask: str
    ideal_answer: str
    skills_being_evaluated: list[str] = Field(default_factory=list)
    improvement_advice: str
    practice_id: str | None = None


class ProgressAnalysis(BaseModel):
    improved_areas: list[str] = Field(default_factory=list)
    declining_areas: list[str] = Field(default_factory=list)
    recurring_weaknesses: list[str] = Field(default_factory=list)
    growth_summary: str = ""
    next_focus_areas: list[str] = Field(default_factory=list)


class InterviewReport(BaseModel):
    session_id: str
    verdict: Literal[
        "Likely Convert",
        "Borderline",
        "Needs Improvement",
        "Waitlist",
        "Borderline Admit",
        "Strong Admit",
        "Strong Hire",
        "Lean Hire",
        "Lean Reject",
        "Strong Reject",
    ]
    overall_score: float
    executive_summary: str
    strengths: list[str]
    weaknesses: list[str]
    panel_concerns: list[str]
    dimensions: list[DimensionScore]
    transcript_evidence: list[TranscriptEvidence] = Field(default_factory=list)
    recommended_improvements: list[str] = Field(default_factory=list)
    panel_comments: list[str] = Field(default_factory=list)
    benchmarking: list[BenchmarkCategory] = Field(default_factory=list)
    benchmark_disclaimer: str = (
        "Interview Preparedness Benchmark: these comparisons are preparation indicators only, not admission predictions or admit probabilities."
    )
    mba_readiness_assessment: str = ""
    coaching_items: list[FollowUpCoachingItem] = Field(default_factory=list)
    progress: ProgressAnalysis | None = None
    feedback_to_candidate: str
    transcript: list[TranscriptTurn]


class EndSessionResponse(BaseModel):
    session_id: str
    status: InterviewStatus
    report: InterviewReport


class AuthenticatedUser(BaseModel):
    id: str
    email: str | None = None
    full_name: str = "Candidate"
    avatar_url: str | None = None
    provider: str = "email"
    is_demo: bool = False


class UserProfileResponse(BaseModel):
    user: AuthenticatedUser
    profile: dict[str, Any] | None = None
    resume: ResumeRecord | None = None


class InterviewHistoryItem(BaseModel):
    session_id: str
    interview_date: datetime
    overall_score: float | None = None
    verdict: str | None = None
    duration_seconds: int = 0
    interview_type: str = "IIM MBA Panel"
    status: InterviewStatus


class ProgressPoint(BaseModel):
    report_id: str | None = None
    created_at: datetime
    communication: float | None = None
    leadership: float | None = None
    business_awareness: float | None = None
    mba_fit: float | None = None
    career_clarity: float | None = None
    academic_depth: float | None = None


class ProgressDashboardResponse(BaseModel):
    points: list[ProgressPoint]
    latest: ProgressAnalysis


class ReportComparisonResponse(BaseModel):
    left: InterviewReport
    right: InterviewReport
    score_changes: list[str]
    improved_areas: list[str]
    remaining_weaknesses: list[str]
    panel_observations: list[str]


class PracticeAgainResponse(BaseModel):
    practice_id: str
    practiced_count: int
    question: str
