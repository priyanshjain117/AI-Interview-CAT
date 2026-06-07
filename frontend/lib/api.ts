import type {
  EndSessionResponse,
  InterviewHistoryItem,
  InterviewReport,
  InterviewTurnResponse,
  ProgressDashboardResponse,
  ReportComparisonResponse,
  ResumeRecord,
  ResumeUploadResponse,
  SessionResponse,
  TranscriptionResponse,
  UserProfileResponse
} from "@/lib/types";
import { supabase } from "@/lib/supabase";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function apiUrl(path: string) {
  if (path.startsWith("http")) {
    return path;
  }
  return `${API_BASE}${path}`;
}

async function authHeaders() {
  const headers = new Headers();
  const session = supabase ? (await supabase.auth.getSession()).data.session : null;
  if (session?.access_token) {
    headers.set("Authorization", `Bearer ${session.access_token}`);
  }
  return headers;
}

async function request<T>(path: string, init?: RequestInit, json = true): Promise<T> {
  const auth = await authHeaders();
  const headers = new Headers(init?.headers);
  auth.forEach((value, key) => headers.set(key, value));
  if (json && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(apiUrl(path), {
    ...init,
    headers
  });

  if (!response.ok) {
    const body = await response.text();
    try {
      const parsed = JSON.parse(body) as { detail?: string | { msg?: string }[] };
      if (typeof parsed.detail === "string") {
        throw new Error(parsed.detail);
      }
      if (Array.isArray(parsed.detail) && parsed.detail[0]?.msg) {
        throw new Error(parsed.detail[0].msg);
      }
    } catch (err) {
      if (err instanceof Error && !(err instanceof SyntaxError)) {
        throw err;
      }
    }
    throw new Error(body || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function createSession(input: {
  name: string;
  goals: string;
  background: string;
  resume_text?: string;
  resume_id?: string | null;
  interview_type?: string;
}) {
  return request<SessionResponse>("/sessions", {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export function getMe() {
  return request<UserProfileResponse>("/me");
}

export function getResume() {
  return request<ResumeRecord | null>("/resume");
}

export function uploadResume(input: {
  file: File;
  name: string;
  goals: string;
  background: string;
}) {
  const formData = new FormData();
  formData.append("file", input.file);
  formData.append("name", input.name || "Candidate");
  formData.append("goals", input.goals);
  formData.append("background", input.background);

  return request<ResumeUploadResponse>(
    "/resume/upload",
    {
      method: "POST",
      body: formData
    },
    false
  );
}

export function deleteResume() {
  return request<{ deleted: boolean }>("/resume", {
    method: "DELETE"
  });
}

export function startSession(sessionId: string) {
  return request<InterviewTurnResponse>(`/sessions/${sessionId}/start`, {
    method: "POST",
    body: JSON.stringify({})
  });
}

export function sendCandidateTurn(sessionId: string, transcript: string) {
  return request<InterviewTurnResponse>(`/sessions/${sessionId}/turn`, {
    method: "POST",
    body: JSON.stringify({ transcript })
  });
}

export function getReport(sessionId: string) {
  return request<InterviewReport>(`/sessions/${sessionId}/report`);
}

export function endSession(sessionId: string) {
  return request<EndSessionResponse>(`/sessions/${sessionId}/end`, {
    method: "POST",
    body: JSON.stringify({})
  });
}

export function transcribeAudio(file: Blob) {
  const formData = new FormData();
  formData.append("file", file, "answer.webm");

  return request<TranscriptionResponse>(
    "/speech/transcribe",
    {
      method: "POST",
      body: formData
    },
    false
  );
}

export function getHistory() {
  return request<InterviewHistoryItem[]>("/history");
}

export function getProgress() {
  return request<ProgressDashboardResponse>("/progress");
}

export function compareReports(leftSessionId: string, rightSessionId: string) {
  const params = new URLSearchParams({
    left_session_id: leftSessionId,
    right_session_id: rightSessionId
  });
  return request<ReportComparisonResponse>(`/reports/compare?${params.toString()}`);
}

export function practiceAgain(practiceId: string) {
  return request<{ practice_id: string; practiced_count: number; question: string }>(
    `/practice/${practiceId}`,
    {
      method: "POST",
      body: JSON.stringify({})
    }
  );
}
