from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


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


class SessionResponse(BaseModel):
    session_id: str
    status: InterviewStatus
    candidate: CandidateProfile
    interviewers: list[InterviewerState]


class CandidateTurnRequest(BaseModel):
    transcript: str = Field(min_length=1)


class ResumeUploadResponse(BaseModel):
    filename: str
    extracted_text: str
    profile: CandidateProfile


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


class InterviewReport(BaseModel):
    session_id: str
    verdict: Literal["Strong Hire", "Lean Hire", "Lean Reject", "Strong Reject"]
    overall_score: float
    strengths: list[str]
    weaknesses: list[str]
    panel_concerns: list[str]
    dimensions: list[DimensionScore]
    feedback_to_candidate: str
    transcript: list[TranscriptTurn]
