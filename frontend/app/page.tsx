"use client";

import { useState } from "react";
import { FileText, ShieldCheck } from "lucide-react";
import { InterviewRoom } from "@/components/InterviewRoom";
import { createSession } from "@/lib/api";
import type { SessionResponse } from "@/lib/types";

export default function Home() {
  const [name, setName] = useState("");
  const [background, setBackground] = useState("");
  const [goals, setGoals] = useState("");
  const [resumeText, setResumeText] = useState("");
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function readResume(file: File | undefined) {
    if (!file) {
      return;
    }
    if (file.type === "text/plain") {
      setResumeText(await file.text());
      return;
    }
    setResumeText(
      `Uploaded resume: ${file.name}. PDF extraction is handled by the backend integration phase.`
    );
  }

  async function enterRoom() {
    setLoading(true);
    setError("");
    try {
      const created = await createSession({
        name: name || "Candidate",
        background,
        goals,
        resume_text: resumeText
      });
      setSession(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create interview session.");
    } finally {
      setLoading(false);
    }
  }

  if (session) {
    return <InterviewRoom session={session} />;
  }

  return (
    <main className="min-h-screen bg-slate-50 px-5 py-8 text-slate-950">
      <div className="mx-auto grid max-w-6xl gap-8 lg:grid-cols-[0.9fr_1.1fr]">
        <section className="flex flex-col justify-center">
          <p className="mb-3 text-sm font-semibold uppercase tracking-wide text-navy-700">
            PANELIQ
          </p>
          <h1 className="text-4xl font-semibold tracking-tight text-slate-950">
            Join a realistic IIM admission panel.
          </h1>
          <p className="mt-5 max-w-xl text-lg leading-8 text-slate-600">
            Upload your resume, enter a professional interview room, answer by voice, and face
            academic, pressure, and MBA-style questioning from a shared-memory panel.
          </p>
          <div className="mt-8 grid gap-3 text-sm text-slate-700">
            <div className="flex items-center gap-3">
              <ShieldCheck className="h-5 w-5 text-navy-700" />
              Real webcam and microphone flow.
            </div>
            <div className="flex items-center gap-3">
              <ShieldCheck className="h-5 w-5 text-navy-700" />
              No chat bubbles, no generic assistant interface.
            </div>
            <div className="flex items-center gap-3">
              <ShieldCheck className="h-5 w-5 text-navy-700" />
              Evidence-based panel report after the simulation.
            </div>
          </div>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-panel">
          <div className="mb-6">
            <h2 className="text-2xl font-semibold">Candidate Intake</h2>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              This prepares the panel memory before the voice interview begins.
            </p>
          </div>

          <div className="space-y-4">
            <label className="block">
              <span className="text-sm font-semibold text-slate-700">Name</span>
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 outline-none ring-navy-700 focus:ring-2"
                placeholder="Priyanshu Jain"
              />
            </label>

            <label className="block">
              <span className="text-sm font-semibold text-slate-700">Background</span>
              <textarea
                value={background}
                onChange={(event) => setBackground(event.target.value)}
                className="mt-2 min-h-24 w-full resize-none rounded-md border border-slate-300 px-3 py-2 outline-none ring-navy-700 focus:ring-2"
                placeholder="Final-year CSE student, internships, projects, interests..."
              />
            </label>

            <label className="block">
              <span className="text-sm font-semibold text-slate-700">MBA goals</span>
              <textarea
                value={goals}
                onChange={(event) => setGoals(event.target.value)}
                className="mt-2 min-h-24 w-full resize-none rounded-md border border-slate-300 px-3 py-2 outline-none ring-navy-700 focus:ring-2"
                placeholder="Product management, consulting, strategy, entrepreneurship..."
              />
            </label>

            <label className="flex cursor-pointer items-center justify-between gap-4 rounded-md border border-dashed border-slate-300 p-4">
              <div className="flex items-center gap-3">
                <FileText className="h-5 w-5 text-navy-700" />
                <div>
                  <p className="text-sm font-semibold">Upload resume</p>
                  <p className="text-xs text-slate-500">TXT reads locally. PDF parser is backend-ready.</p>
                </div>
              </div>
              <input
                type="file"
                accept=".txt,.pdf"
                className="hidden"
                onChange={(event) => readResume(event.target.files?.[0])}
              />
            </label>

            {resumeText ? (
              <p className="rounded-md bg-slate-50 p-3 text-sm text-slate-600">
                Resume context loaded into panel memory.
              </p>
            ) : null}

            <button
              onClick={enterRoom}
              disabled={loading}
              className="w-full rounded-md bg-navy-900 px-4 py-3 text-sm font-semibold text-white hover:bg-navy-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? "Preparing panel..." : "Enter Interview Room"}
            </button>
            {error ? <p className="text-sm font-medium text-red-700">{error}</p> : null}
          </div>
        </section>
      </div>
    </main>
  );
}
