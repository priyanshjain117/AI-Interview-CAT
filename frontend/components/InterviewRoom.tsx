"use client";

import { useMemo, useRef, useState } from "react";
import { Loader2, Mic, MicOff, PhoneOff, Play } from "lucide-react";
import { CandidateCamera } from "@/components/CandidateCamera";
import { InterviewerCard } from "@/components/InterviewerCard";
import { SessionTimer } from "@/components/SessionTimer";
import { SubtitlePanel } from "@/components/SubtitlePanel";
import { getReport, sendCandidateTurn, startSession } from "@/lib/api";
import type {
  InterviewReport,
  InterviewStatus,
  InterviewTurnResponse,
  Interviewer,
  InterviewerId,
  SessionResponse
} from "@/lib/types";

type VoiceStatus = "idle" | "listening" | "processing" | "speaking";

export function InterviewRoom({ session }: { session: SessionResponse }) {
  const [activeInterviewerId, setActiveInterviewerId] = useState<InterviewerId | null>(null);
  const [subtitle, setSubtitle] = useState("");
  const [candidateDraft, setCandidateDraft] = useState("");
  const [voiceStatus, setVoiceStatus] = useState<VoiceStatus>("idle");
  const [interviewStatus, setInterviewStatus] = useState<InterviewStatus>(session.status);
  const [report, setReport] = useState<InterviewReport | null>(null);
  const [error, setError] = useState("");
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  const activeInterviewer = useMemo(
    () => session.interviewers.find((interviewer) => interviewer.id === activeInterviewerId),
    [activeInterviewerId, session.interviewers]
  );

  async function beginInterview() {
    setError("");
    try {
      await navigator.mediaDevices.getUserMedia({ audio: true });
      const response = await startSession(session.session_id);
      applyPanelTurn(response);
      speak(response.subtitle_text);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start the interview.");
    }
  }

  function applyPanelTurn(response: InterviewTurnResponse) {
    setActiveInterviewerId(response.active_interviewer_id);
    setSubtitle(response.subtitle_text);
    setInterviewStatus(response.status);
  }

  function speak(text: string) {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.92;
    utterance.pitch = 0.95;
    utterance.onstart = () => setVoiceStatus("speaking");
    utterance.onend = () => {
      setVoiceStatus(interviewStatus === "completed" ? "idle" : "idle");
    };
    window.speechSynthesis.speak(utterance);
  }

  function startListening() {
    setError("");
    const Recognition = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!Recognition) {
      setError("This browser does not support live speech recognition. Use Chrome or Edge.");
      return;
    }

    const recognition = new Recognition();
    recognition.lang = "en-IN";
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.onstart = () => setVoiceStatus("listening");
    recognition.onerror = () => {
      setVoiceStatus("idle");
      setError("Speech recognition stopped. Please try again.");
    };
    recognition.onresult = (event) => {
      const text = Array.from(event.results)
        .map((result) => result[0]?.transcript ?? "")
        .join(" ")
        .trim();
      setCandidateDraft(text);
    };
    recognition.onend = () => {
      setVoiceStatus("idle");
    };

    recognitionRef.current = recognition;
    recognition.start();
  }

  function stopListening() {
    recognitionRef.current?.stop();
    setVoiceStatus("idle");
  }

  async function submitAnswer() {
    if (!candidateDraft.trim()) {
      return;
    }

    setVoiceStatus("processing");
    setError("");
    try {
      const response = await sendCandidateTurn(session.session_id, candidateDraft.trim());
      setCandidateDraft("");
      applyPanelTurn(response);
      speak(response.subtitle_text);
      if (response.status === "completed") {
        const nextReport = await getReport(session.session_id);
        setReport(nextReport);
      }
    } catch (err) {
      setVoiceStatus("idle");
      setError(err instanceof Error ? err.message : "Unable to submit your answer.");
    }
  }

  async function endInterview() {
    window.speechSynthesis.cancel();
    stopListening();
    const nextReport = await getReport(session.session_id);
    setReport(nextReport);
    setInterviewStatus("completed");
    setVoiceStatus("idle");
  }

  return (
    <main className="min-h-screen bg-slate-50 px-5 py-6 text-slate-950 lg:px-8">
      <header className="mx-auto mb-6 flex max-w-7xl flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-navy-700">PANELIQ</p>
          <h1 className="text-2xl font-semibold tracking-tight">IIM Panel Interview Room</h1>
        </div>
        <div className="flex items-center gap-3">
          <SessionTimer running={interviewStatus === "in_progress"} />
          <div className="rounded-full bg-white px-4 py-2 text-sm font-medium text-slate-600">
            {activeInterviewer ? `Active: ${activeInterviewer.role}` : "Panel ready"}
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-5 lg:grid-cols-2">
        {session.interviewers.map((interviewer: Interviewer) => (
          <InterviewerCard
            key={interviewer.id}
            interviewer={interviewer}
            isActive={interviewer.id === activeInterviewerId}
            isSpeaking={voiceStatus === "speaking" && interviewer.id === activeInterviewerId}
          />
        ))}
        <CandidateCamera />
      </div>

      <div className="mx-auto mt-5 max-w-7xl space-y-5">
        <SubtitlePanel text={subtitle} status={voiceStatus} />

        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold">Microphone Controls</h2>
              <p className="text-sm text-slate-500">
                Speak naturally. Review the captured transcript, then submit your answer to the panel.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {interviewStatus === "ready" ? (
                <button
                  onClick={beginInterview}
                  className="inline-flex items-center gap-2 rounded-md bg-navy-900 px-4 py-2 text-sm font-semibold text-white hover:bg-navy-800"
                >
                  <Play className="h-4 w-4" />
                  Start Interview
                </button>
              ) : null}
              <button
                onClick={voiceStatus === "listening" ? stopListening : startListening}
                disabled={interviewStatus !== "in_progress" || voiceStatus === "speaking"}
                className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {voiceStatus === "listening" ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
                {voiceStatus === "listening" ? "Stop Listening" : "Start Listening"}
              </button>
              <button
                onClick={submitAnswer}
                disabled={!candidateDraft.trim() || voiceStatus === "processing"}
                className="inline-flex items-center gap-2 rounded-md bg-navy-900 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                {voiceStatus === "processing" ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Submit Answer
              </button>
              <button
                onClick={endInterview}
                disabled={interviewStatus === "ready"}
                className="inline-flex items-center gap-2 rounded-md border border-red-200 px-4 py-2 text-sm font-semibold text-red-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <PhoneOff className="h-4 w-4" />
                End
              </button>
            </div>
          </div>

          <textarea
            value={candidateDraft}
            onChange={(event) => setCandidateDraft(event.target.value)}
            placeholder="Your live speech transcript appears here."
            className="min-h-28 w-full resize-none rounded-md border border-slate-300 bg-white p-3 text-base leading-7 outline-none ring-navy-700 focus:ring-2"
          />
          {error ? <p className="mt-3 text-sm font-medium text-red-700">{error}</p> : null}
        </section>

        {report ? (
          <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-panel">
            <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="text-sm font-semibold uppercase tracking-wide text-navy-700">
                  Panel Report
                </p>
                <h2 className="text-2xl font-semibold">{report.verdict}</h2>
              </div>
              <div className="text-right">
                <p className="text-sm text-slate-500">Overall score</p>
                <p className="text-3xl font-semibold text-navy-900">{report.overall_score}/10</p>
              </div>
            </div>
            <p className="mb-5 leading-7 text-slate-700">{report.feedback_to_candidate}</p>
            <div className="grid gap-4 md:grid-cols-2">
              {report.dimensions.map((dimension) => (
                <div key={dimension.name} className="rounded-md border border-slate-200 p-4">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <h3 className="font-semibold">{dimension.name}</h3>
                    <span className="font-semibold text-navy-900">{dimension.score ?? "N/A"}</span>
                  </div>
                  <p className="text-sm leading-6 text-slate-600">{dimension.advice}</p>
                </div>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </main>
  );
}
