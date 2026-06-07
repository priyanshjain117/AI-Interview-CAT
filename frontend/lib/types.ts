export type InterviewerId = "academic" | "pressure" | "mba";

export type InterviewStatus = "ready" | "in_progress" | "completed";

export type VoiceStatus = "IDLE" | "LISTENING" | "PROCESSING" | "AI_SPEAKING" | "COMPLETED" | "ERROR";

export type Interviewer = {
  id: InterviewerId;
  name: string;
  role: string;
  focus: string;
};

export type TranscriptTurn = {
  id: string;
  speaker: "candidate" | "interviewer";
  text: string;
  created_at: string;
  interviewer_id?: InterviewerId | null;
};

export type SessionResponse = {
  session_id: string;
  status: InterviewStatus;
  candidate: {
    name: string;
    resume_text: string;
    goals: string;
    background: string;
    education: string[];
    projects: string[];
    internships: string[];
    achievements: string[];
    certifications: string[];
    skills: string[];
    career_goals: string[];
    notable_resume_claims: string[];
  };
  interviewers: Interviewer[];
  max_duration_seconds: number;
};

export type InterviewTurnResponse = {
  session_id: string;
  active_interviewer_id: InterviewerId;
  speaker_reason: string;
  subtitle_text: string;
  audio_url: string | null;
  voice_strategy: "browser_speech_synthesis" | "server_audio";
  status: InterviewStatus;
  transcript: TranscriptTurn[];
};

export type InterviewReport = {
  session_id: string;
  verdict:
    | "Likely Convert"
    | "Borderline"
    | "Needs Improvement"
    | "Waitlist"
    | "Borderline Admit"
    | "Strong Admit"
    | "Strong Hire"
    | "Lean Hire"
    | "Lean Reject"
    | "Strong Reject";
  overall_score: number;
  executive_summary: string;
  strengths: string[];
  weaknesses: string[];
  panel_concerns: string[];
  feedback_to_candidate: string;
  dimensions: {
    name: string;
    score: number | null;
    evidence: string;
    strengths: string[];
    weaknesses: string[];
    advice: string;
  }[];
  transcript_evidence: {
    topic: string;
    evidence: string;
    panel_interpretation: string;
  }[];
  recommended_improvements: string[];
  panel_comments: string[];
  benchmarking: {
    category: "Typical IIM Convert Candidate" | "Strong IIM ABC Candidate" | "Average CAT Aspirant";
    communication: string;
    leadership: string;
    business_awareness: string;
    academic_depth: string;
    mba_fit: string;
    notes: string;
  }[];
  benchmark_disclaimer: string;
  mba_readiness_assessment: string;
  coaching_items: {
    weakness: string;
    question: string;
    why_panel_would_ask: string;
    ideal_answer: string;
    skills_being_evaluated: string[];
    improvement_advice: string;
    practice_id: string | null;
  }[];
  progress: ProgressAnalysis | null;
};

export type ResumeUploadResponse = {
  resume_id: string | null;
  filename: string;
  extracted_text: string;
  profile: SessionResponse["candidate"];
  version: number;
  parsed_at: string;
};

export type TranscriptionResponse = {
  transcript: string;
  language: string | null;
  duration_seconds: number | null;
};

export type EndSessionResponse = {
  session_id: string;
  status: InterviewStatus;
  report: InterviewReport;
};

export type ResumeRecord = {
  id: string;
  filename: string;
  extracted_text: string;
  version: number;
  is_active: boolean;
  parsed_at: string;
  created_at: string;
};

export type UserProfileResponse = {
  user: {
    id: string;
    email: string | null;
    full_name: string;
    avatar_url: string | null;
    provider: string;
    is_demo: boolean;
  };
  profile: SessionResponse["candidate"] | null;
  resume: ResumeRecord | null;
};

export type InterviewHistoryItem = {
  session_id: string;
  interview_date: string;
  overall_score: number | null;
  verdict: string | null;
  duration_seconds: number;
  interview_type: string;
  status: InterviewStatus;
};

export type ProgressAnalysis = {
  improved_areas: string[];
  declining_areas: string[];
  recurring_weaknesses: string[];
  growth_summary: string;
  next_focus_areas: string[];
};

export type ProgressDashboardResponse = {
  points: {
    report_id: string | null;
    created_at: string;
    communication: number | null;
    leadership: number | null;
    business_awareness: number | null;
    mba_fit: number | null;
    career_clarity: number | null;
    academic_depth: number | null;
  }[];
  latest: ProgressAnalysis;
};

export type BenchmarkGapDimension = {
  dimension: string;
  your_score: number;
  ref_range: string;
  gap: number;
  status: "above" | "within" | "below";
};

export type BenchmarkGapProfile = {
  profile: string;
  dimensions: BenchmarkGapDimension[];
};

export type ReportComparisonResponse = {
  left: InterviewReport;
  right: InterviewReport;
  score_changes: string[];
  improved_areas: string[];
  remaining_weaknesses: string[];
  regressions: string[];
  panel_observations: string[];
  benchmark_gaps: BenchmarkGapProfile[];
};
