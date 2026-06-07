"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Mic, MicOff, PhoneOff, Play } from "lucide-react";
import { CandidateCamera } from "@/components/CandidateCamera";
import { InterviewerCard } from "@/components/InterviewerCard";
import { SessionTimer } from "@/components/SessionTimer";
import { SubtitlePanel } from "@/components/SubtitlePanel";
import { apiUrl, endSession, getReport, sendCandidateTurn, startSession, transcribeAudio } from "@/lib/api";
import type {
  InterviewReport,
  InterviewStatus,
  InterviewTurnResponse,
  Interviewer,
  InterviewerId,
  SessionResponse
} from "@/lib/types";

type VoiceStatus = "idle" | "listening" | "processing" | "speaking";

export function InterviewRoom({ session, onExit }: { session: SessionResponse; onExit?: () => void }) {
  const [activeInterviewerId, setActiveInterviewerId] = useState<InterviewerId | null>(null);
  const [subtitle, setSubtitle] = useState("");
  const [candidateDraft, setCandidateDraft] = useState("");
  const [voiceStatus, setVoiceStatus] = useState<VoiceStatus>("idle");
  const [interviewStatus, setInterviewStatus] = useState<InterviewStatus>(session.status);
  const [report, setReport] = useState<InterviewReport | null>(null);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);
  const [ending, setEnding] = useState(false);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const playbackRef = useRef<HTMLAudioElement | null>(null);

  const activeInterviewer = useMemo(
    () => session.interviewers.find((interviewer) => interviewer.id === activeInterviewerId),
    [activeInterviewerId, session.interviewers]
  );

  useEffect(() => {
    return () => {
      stopPlayback();
      stopRecording(false);
      stopMicrophone();
    };
  }, []);

  async function beginInterview() {
    if (starting) {
      return;
    }
    setStarting(true);
    setError("");
    try {
      await getMicrophoneStream();
      const response = await startSession(session.session_id);
      applyPanelTurn(response);
      playPanelAudio(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start the interview.");
      setVoiceStatus("idle");
    } finally {
      setStarting(false);
    }
  }

  function applyPanelTurn(response: InterviewTurnResponse) {
    setActiveInterviewerId(response.active_interviewer_id);
    setSubtitle(response.subtitle_text);
    setInterviewStatus(response.status);
  }

  function stopPlayback() {
    playbackRef.current?.pause();
    playbackRef.current = null;
    window.speechSynthesis.cancel();
  }

  function playPanelAudio(response: InterviewTurnResponse) {
    stopPlayback();
    const text = response.subtitle_text;

    if (response.voice_strategy === "server_audio" && response.audio_url) {
      const audio = new Audio(apiUrl(response.audio_url));
      playbackRef.current = audio;
      audio.onplay = () => setVoiceStatus("speaking");
      audio.onended = () => setVoiceStatus("idle");
      audio.onerror = () => speak(text);
      audio.play().catch(() => speak(text));
      return;
    }

    speak(text);
  }

  function speak(text: string) {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.92;
    utterance.pitch = 0.95;
    utterance.onstart = () => setVoiceStatus("speaking");
    utterance.onend = () => setVoiceStatus("idle");
    utterance.onerror = () => setVoiceStatus("idle");
    window.speechSynthesis.speak(utterance);
  }

  async function getMicrophoneStream() {
    const activeStream = streamRef.current;
    if (activeStream?.active) {
      return activeStream;
    }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;
    return stream;
  }

  function stopMicrophone() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }

  function recorderMimeType() {
    if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
      return "audio/webm;codecs=opus";
    }
    if (MediaRecorder.isTypeSupported("audio/webm")) {
      return "audio/webm";
    }
    return "";
  }

  async function startRecording() {
    if (
      voiceStatus === "listening" ||
      voiceStatus === "processing" ||
      voiceStatus === "speaking" ||
      interviewStatus !== "in_progress"
    ) {
      return;
    }

    setError("");
    stopPlayback();
    try {
      const stream = await getMicrophoneStream();
      audioChunksRef.current = [];
      const mimeType = recorderMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      recorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
      recorder.onerror = () => {
        setError("Recording failed. Please try again.");
        setVoiceStatus("idle");
        stopMicrophone();
      };
      recorder.onstop = () => {
        processRecording();
      };
      recorder.start();
      setVoiceStatus("listening");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to access the microphone.");
      setVoiceStatus("idle");
      stopMicrophone();
    }
  }

  function stopRecording(shouldProcess = true) {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      if (!shouldProcess) {
        recorder.onstop = null;
      }
      recorder.stop();
    }
    recorderRef.current = null;
    if (!shouldProcess) {
      setVoiceStatus("idle");
    }
  }

  async function processRecording() {
    const chunks = audioChunksRef.current;
    audioChunksRef.current = [];
    stopMicrophone();
    if (!chunks.length) {
      setVoiceStatus("idle");
      setError("No audio was recorded. Please try again.");
      return;
    }

    setVoiceStatus("processing");
    setError("");
    try {
      const audio = new Blob(chunks, { type: chunks[0]?.type || "audio/webm" });
      const transcription = await transcribeAudio(audio);
      setCandidateDraft(transcription.transcript);
      setSubtitle(transcription.transcript);
      setVoiceStatus("idle");
    } catch (err) {
      setVoiceStatus("idle");
      setError(err instanceof Error ? err.message : "Unable to transcribe your answer.");
    }
  }

  async function submitAnswer() {
    if (!candidateDraft.trim()) {
      return;
    }

    setVoiceStatus("processing");
    setError("");
    try {
      stopPlayback();
      const response = await sendCandidateTurn(session.session_id, candidateDraft.trim());
      setCandidateDraft("");
      applyPanelTurn(response);
      playPanelAudio(response);
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
    if (ending || interviewStatus === "ready") {
      return;
    }
    setEnding(true);
    setError("");
    stopPlayback();
    stopRecording(false);
    stopMicrophone();
    setVoiceStatus("processing");
    try {
      const response = await endSession(session.session_id);
      setReport(response.report);
      setInterviewStatus(response.status);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to end the interview.");
    } finally {
      setVoiceStatus("idle");
      setEnding(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#f8fafc] text-slate-900">
      <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-slate-200 bg-white px-5">
        <div>
          <p className="text-xs font-bold tracking-[0.14em] uppercase text-navy-700">PANELIQ</p>
          <p className="text-[11px] text-slate-400">IIM Panel Interview Room</p>
        </div>
        <div className="flex items-center gap-3">
          <SessionTimer
            running={interviewStatus === "in_progress"}
            maxSeconds={session.max_duration_seconds ?? 1500}
            onTimeUp={() => {
              if (interviewStatus === "in_progress" && !ending) endInterview();
            }}
          />
          <div className="rounded-full border border-slate-200 bg-white px-3.5 py-1.5 text-xs font-medium text-slate-600">
            {activeInterviewer ? `${activeInterviewer.name} · ${activeInterviewer.role}` : "Panel ready"}
          </div>
          {onExit && (
            <button onClick={onExit} className="btn btn-secondary text-xs px-3 py-1.5">
              Exit
            </button>
          )}
        </div>
      </header>

      {/* Time progress bar */}
      {interviewStatus === "in_progress" && (
        <TimeProgressBar
          maxSeconds={session.max_duration_seconds ?? 1500}
          running={interviewStatus === "in_progress"}
        />
      )}
      <div className="mx-auto grid max-w-6xl gap-5 px-5 pb-4 lg:grid-cols-2">
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

      <div className="mx-auto mt-5 max-w-6xl space-y-5 px-5 pb-8">
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
                  disabled={starting}
                  className="inline-flex items-center gap-2 rounded-md bg-navy-900 px-4 py-2 text-sm font-semibold text-white hover:bg-navy-800"
                >
                  {starting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                  {starting ? "Starting..." : "Start Interview"}
                </button>
              ) : null}
              <button
                onClick={voiceStatus === "listening" ? () => stopRecording(true) : startRecording}
                disabled={
                  interviewStatus !== "in_progress" ||
                  voiceStatus === "speaking" ||
                  voiceStatus === "processing"
                }
                className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {voiceStatus === "listening" ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
                {voiceStatus === "listening" ? "Finish Answer" : "Start Answer"}
              </button>
              <button
                onClick={submitAnswer}
                disabled={
                  !candidateDraft.trim() ||
                  voiceStatus === "processing" ||
                  voiceStatus === "listening" ||
                  voiceStatus === "speaking" ||
                  interviewStatus !== "in_progress"
                }
                className="inline-flex items-center gap-2 rounded-md bg-navy-900 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                {voiceStatus === "processing" ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Submit Answer
              </button>
              <button
                onClick={endInterview}
                disabled={interviewStatus === "ready" || ending}
                className="inline-flex items-center gap-2 rounded-md border border-red-200 px-4 py-2 text-sm font-semibold text-red-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {ending ? <Loader2 className="h-4 w-4 animate-spin" /> : <PhoneOff className="h-4 w-4" />}
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
          <div className="card p-6 animate-fade-in">
            <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="text-label mb-1">Panel Report</p>
                <h2 className="text-2xl font-bold text-slate-900">{report.verdict}</h2>
              </div>
              <div className="flex items-end gap-4">
                <div className="text-right">
                  <p className="text-xs text-slate-400">Overall score</p>
                  <p className={`text-3xl font-bold tabular-nums ${
                    report.overall_score >= 8 ? "text-emerald-700" : report.overall_score >= 7 ? "text-navy-700" : report.overall_score >= 5.5 ? "text-amber-700" : "text-rose-700"
                  }`}>{report.overall_score}<span className="text-lg font-normal text-slate-400">/10</span></p>
                </div>
              </div>
            </div>
            <p className="mb-5 leading-7 text-slate-600">
              {report.executive_summary || report.feedback_to_candidate}
            </p>
            <div className="mb-5 grid gap-4 md:grid-cols-2">
              <div>
                <h3 className="mb-2 text-sm font-semibold text-slate-800">Strengths</h3>
                <ul className="space-y-2">
                  {report.strengths.map((item) => (
                    <li key={item} className="flex items-start gap-2 text-sm text-slate-600">
                      <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-emerald-500" />{item}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h3 className="mb-2 text-sm font-semibold text-slate-800">Weaknesses</h3>
                <ul className="space-y-2">
                  {report.weaknesses.map((item) => (
                    <li key={item} className="flex items-start gap-2 text-sm text-slate-600">
                      <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-rose-500" />{item}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              {report.dimensions.map((dimension) => (
                <div key={dimension.name} className="rounded-xl border border-slate-200 p-4">
                  <div className="mb-1.5 flex items-center justify-between gap-3">
                    <h3 className="text-sm font-semibold text-slate-800">{dimension.name}</h3>
                    <span className={`text-sm font-bold ${
                      dimension.score !== null && dimension.score >= 8 ? "text-emerald-700" : dimension.score !== null && dimension.score >= 7 ? "text-navy-700" : dimension.score !== null && dimension.score >= 5.5 ? "text-amber-700" : "text-slate-400"
                    }`}>{dimension.score ?? "N/A"}</span>
                  </div>
                  <p className="text-sm leading-6 text-slate-500">{dimension.advice}</p>
                </div>
              ))}
            </div>
            {onExit && (
              <div className="mt-6 flex gap-3">
                <button onClick={onExit} className="btn btn-primary">
                  Return to Dashboard
                </button>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}

/* ─── Time Progress Bar ──────────────────────────────────────────── */
function TimeProgressBar({ maxSeconds, running }: { maxSeconds: number; running: boolean }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(id);
  }, [running]);

  const pct = Math.min(100, (elapsed / maxSeconds) * 100);
  const remaining = maxSeconds - elapsed;

  let barColor = "bg-emerald-500";
  if (remaining <= 60)  barColor = "bg-red-500 time-warning";
  else if (remaining <= 300) barColor = "bg-amber-400";

  return (
    <div className="h-1 w-full bg-slate-100" title={`${Math.round(remaining / 60)} min remaining`}>
      <div
        className={`h-full transition-all duration-1000 ease-linear ${barColor}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
