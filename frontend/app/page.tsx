"use client";

import { useEffect, useState } from "react";
import {
  BarChart3,
  ArrowLeft,
  Download,
  FileText,
  History,
  Loader2,
  LogOut,
  Play,
  RefreshCw,
  Trash2
} from "lucide-react";
import type { Session } from "@supabase/supabase-js";
import { InterviewRoom } from "@/components/InterviewRoom";
import {
  apiUrl,
  compareReports,
  createSession,
  deleteResume,
  getHistory,
  getMe,
  getProgress,
  getReport,
  practiceAgain,
  uploadResume
} from "@/lib/api";
import { supabase } from "@/lib/supabase";
import type {
  InterviewHistoryItem,
  InterviewReport,
  ProgressDashboardResponse,
  ReportComparisonResponse,
  SessionResponse,
  UserProfileResponse
} from "@/lib/types";

const DEMO_EMAIL = process.env.NEXT_PUBLIC_DEMO_EMAIL ?? "demo@paneliq.local";
const DEMO_PASSWORD = process.env.NEXT_PUBLIC_DEMO_PASSWORD ?? "demo1234";

type View = "dashboard" | "resume" | "history" | "progress" | "compare" | "report";

export default function Home() {
  const [session, setSession] = useState<Session | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [profile, setProfile] = useState<UserProfileResponse | null>(null);
  const [history, setHistory] = useState<InterviewHistoryItem[]>([]);
  const [progress, setProgress] = useState<ProgressDashboardResponse | null>(null);
  const [activeSession, setActiveSession] = useState<SessionResponse | null>(null);
  const [activeReport, setActiveReport] = useState<InterviewReport | null>(null);
  const [comparison, setComparison] = useState<ReportComparisonResponse | null>(null);
  const [view, setView] = useState<View>("dashboard");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [background, setBackground] = useState("");
  const [goals, setGoals] = useState("");

  const signedIn = Boolean(session);
  const completedHistory = history.filter((item) => item.status === "completed" && item.overall_score !== null);

  useEffect(() => {
    if (!supabase) return;
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
    });
    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
    });
    return () => data.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (signedIn && !activeSession) {
      refreshApp();
    }
  }, [signedIn, activeSession]);

  async function refreshApp() {
    setLoading(true);
    setError("");
    try {
      const [me, past, trend] = await Promise.all([getMe(), getHistory(), getProgress()]);
      setProfile(me);
      if (me.profile) {
        setName(me.profile.name);
        setBackground(me.profile.background);
        setGoals(me.profile.goals);
      } else if (me.user.full_name) {
        setName(me.user.full_name);
      }
      setHistory(past);
      setProgress(trend);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load PANELIQ data.");
    } finally {
      setLoading(false);
    }
  }

  async function loginWithEmail() {
    const normalizedEmail = email.trim().toLowerCase();
    if (!supabase) {
      setError("Configure NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY for login.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const { error: authError } = await supabase.auth.signInWithPassword({ email: normalizedEmail, password });
      if (authError) {
        const message = authError.message.toLowerCase();
        if (!message.includes("invalid login credentials") && !message.includes("user not found")) {
          throw authError;
        }
        const { error: signupError } = await supabase.auth.signUp({ email, password });
        if (signupError) {
          throw signupError;
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Email login failed.");
    } finally {
      setLoading(false);
    }
  }

  async function loginWithGoogle() {
    if (!supabase) {
      setError("Configure Supabase Auth environment variables for Google login.");
      return;
    }
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: window.location.origin }
    });
  }

  async function enterDemo() {
    if (!supabase) {
      setError("Supabase is not configured. Cannot log in as demo.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const { error: authError } = await supabase.auth.signInWithPassword({
        email: DEMO_EMAIL,
        password: DEMO_PASSWORD,
      });
      if (authError) throw authError;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Demo login failed.");
    } finally {
      setLoading(false);
    }
  }

  async function signOut() {
    setProfile(null);
    setHistory([]);
    setProgress(null);
    setActiveReport(null);
    setActiveSession(null);
    await supabase?.auth.signOut();
  }

  async function handleResume(file: File | undefined) {
    if (!file) {
      return;
    }
    setLoading(true);
    setError("");
    try {
      await uploadResume({ file, name: name || "Candidate", background, goals });
      await refreshApp();
      setView("dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to upload resume.");
    } finally {
      setLoading(false);
    }
  }

  async function removeResume() {
    setLoading(true);
    setError("");
    try {
      await deleteResume();
      await refreshApp();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete resume.");
    } finally {
      setLoading(false);
    }
  }

  async function beginInterview() {
    if (!profile?.resume) {
      setView("resume");
      setError("Upload a resume once before starting interviews.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const created = await createSession({
        name: name || profile.user.full_name || "Candidate",
        background,
        goals,
        resume_id: profile.resume.id,
        interview_type: "IIM MBA Panel"
      });
      setActiveSession(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create interview session.");
    } finally {
      setLoading(false);
    }
  }

  async function openReport(sessionId: string) {
    setLoading(true);
    setError("");
    try {
      const report = await getReport(sessionId);
      setActiveReport(report);
      setView("report");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to open report.");
    } finally {
      setLoading(false);
    }
  }

  async function runComparison() {
    if (completedHistory.length < 2) {
      return;
    }
    setLoading(true);
    setError("");
    try {
      const oldest = completedHistory[completedHistory.length - 1];
      const newest = completedHistory[0];
      setComparison(await compareReports(oldest.session_id, newest.session_id));
      setView("compare");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to compare reports.");
    } finally {
      setLoading(false);
    }
  }

  if (activeSession) {
    return <InterviewRoom session={activeSession} />;
  }

  if (!signedIn) {
    return (
      <main className="min-h-screen bg-slate-50 px-5 py-8 text-slate-950">
        <div className="mx-auto grid max-w-6xl gap-8 lg:grid-cols-[1fr_0.9fr]">
          <section className="flex flex-col justify-center">
            <p className="mb-3 text-sm font-semibold uppercase tracking-wide text-navy-700">PANELIQ</p>
            <h1 className="text-4xl font-semibold tracking-tight">AI MBA Interview Coaching Platform</h1>
            <p className="mt-5 max-w-xl text-lg leading-8 text-slate-600">
              Sign in, store your resume once, take repeated IIM-style interviews, track progress, practice weaknesses, and download evidence-based reports.
            </p>
            <div className="mt-8 grid gap-3 text-sm text-slate-700">
              <button
                onClick={enterDemo}
                disabled={loading}
                className="inline-flex w-fit items-center gap-2 rounded-md bg-navy-900 px-4 py-3 font-semibold text-white disabled:opacity-60"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                {loading ? "Signing in..." : "Try Demo Account"}
              </button>
              <p className="text-xs text-slate-500">Instantly explore a pre-seeded interview profile with 3 past sessions.</p>
            </div>
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-panel">
            <h2 className="text-2xl font-semibold">Sign in</h2>
            <div className="mt-5 space-y-4">
              <input value={email} onChange={(event) => setEmail(event.target.value)} className="w-full rounded-md border border-slate-300 px-3 py-2 outline-none ring-navy-700 focus:ring-2" placeholder="Email" />
              <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" className="w-full rounded-md border border-slate-300 px-3 py-2 outline-none ring-navy-700 focus:ring-2" placeholder="Password" />
              <button onClick={loginWithEmail} disabled={loading || !email || !password} className="w-full rounded-md bg-navy-900 px-4 py-3 text-sm font-semibold text-white disabled:opacity-50">
                {loading ? "Working..." : "Email Login"}
              </button>
              <button onClick={loginWithGoogle} className="w-full rounded-md border border-slate-300 px-4 py-3 text-sm font-semibold text-slate-800">
                Google Login
              </button>
              {error ? <p className="text-sm font-medium text-red-700">{error}</p> : null}
            </div>
          </section>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-50 px-5 py-6 text-slate-950 lg:px-8">
      <header className="mx-auto mb-6 flex max-w-7xl flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-navy-700">PANELIQ</p>
          <h1 className="text-2xl font-semibold tracking-tight">Interview Coach Dashboard</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {(["dashboard", "resume", "history", "progress"] as View[]).map((item) => (
            <button key={item} onClick={() => setView(item)} className={`rounded-md px-3 py-2 text-sm font-semibold ${view === item ? "bg-navy-900 text-white" : "border border-slate-300 bg-white text-slate-700"}`}>
              {item[0].toUpperCase() + item.slice(1)}
            </button>
          ))}
          <button onClick={signOut} className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700">
            <LogOut className="h-4 w-4" />
            Exit
          </button>
        </div>
      </header>

      <div className="mx-auto max-w-7xl space-y-5">
        {error ? <p className="rounded-md border border-red-200 bg-red-50 p-3 text-sm font-medium text-red-700">{error}</p> : null}
        {loading ? <p className="inline-flex items-center gap-2 text-sm text-slate-600"><Loader2 className="h-4 w-4 animate-spin" /> Loading</p> : null}
        {view !== "dashboard" ? (
          <button
            onClick={() => {
              setView("dashboard");
              setActiveReport(null);
              setComparison(null);
              setError("");
            }}
            className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Dashboard
          </button>
        ) : null}

        {view === "dashboard" ? (
          <Dashboard
            profile={profile}
            history={history}
            progress={progress}
            onStart={beginInterview}
            onReport={openReport}
            onCompare={runComparison}
            loading={loading}
          />
        ) : null}

        {view === "resume" ? (
          <ResumeManager
            profile={profile}
            name={name}
            background={background}
            goals={goals}
            setName={setName}
            setBackground={setBackground}
            setGoals={setGoals}
            onUpload={handleResume}
            onDelete={removeResume}
          />
        ) : null}

        {view === "history" ? <HistoryView history={history} onReport={openReport} onCompare={runComparison} /> : null}
        {view === "progress" ? <ProgressView progress={progress} /> : null}
        {view === "compare" && comparison ? <ComparisonView comparison={comparison} /> : null}
        {view === "report" && activeReport ? <ReportView report={activeReport} /> : null}
      </div>
    </main>
  );
}

function Dashboard(props: {
  profile: UserProfileResponse | null;
  history: InterviewHistoryItem[];
  progress: ProgressDashboardResponse | null;
  loading: boolean;
  onStart: () => void;
  onReport: (sessionId: string) => void;
  onCompare: () => void;
}) {
  const latest = props.history[0];
  return (
    <section className="grid gap-5 lg:grid-cols-[1fr_0.9fr]">
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-panel">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold">Next Interview</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Resume status: {props.profile?.resume ? `${props.profile.resume.filename} v${props.profile.resume.version}` : "No resume uploaded"}
            </p>
          </div>
          <button onClick={props.onStart} disabled={props.loading || !props.profile?.resume} className="inline-flex items-center gap-2 rounded-md bg-navy-900 px-4 py-3 text-sm font-semibold text-white disabled:opacity-50">
            <Play className="h-4 w-4" />
            Start Interview
          </button>
        </div>
        {latest ? (
          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <Metric label="Latest Score" value={latest.overall_score?.toFixed(1) ?? "N/A"} />
            <Metric label="Verdict" value={latest.verdict ?? "Pending"} />
            <Metric label="Attempts" value={String(props.history.length)} />
          </div>
        ) : null}
      </div>
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-panel">
        <h2 className="text-xl font-semibold">Growth Summary</h2>
        <p className="mt-3 text-sm leading-6 text-slate-600">{props.progress?.latest.growth_summary || "Complete interviews to build progress intelligence."}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {latest ? <button onClick={() => props.onReport(latest.session_id)} className="rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold">View Latest Report</button> : null}
          {props.history.length >= 2 ? <button onClick={props.onCompare} className="rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold">Compare Reports</button> : null}
        </div>
      </div>
    </section>
  );
}

function ResumeManager(props: {
  profile: UserProfileResponse | null;
  name: string;
  background: string;
  goals: string;
  setName: (value: string) => void;
  setBackground: (value: string) => void;
  setGoals: (value: string) => void;
  onUpload: (file: File | undefined) => void;
  onDelete: () => void;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-panel">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold">User Resume Profile</h2>
          <p className="mt-2 text-sm text-slate-600">Resume is reused across interviews until you replace or delete it.</p>
        </div>
        {props.profile?.resume ? (
          <button onClick={props.onDelete} className="inline-flex items-center gap-2 rounded-md border border-red-200 px-3 py-2 text-sm font-semibold text-red-700">
            <Trash2 className="h-4 w-4" />
            Delete Resume
          </button>
        ) : null}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-4">
          <input value={props.name} onChange={(event) => props.setName(event.target.value)} className="w-full rounded-md border border-slate-300 px-3 py-2 outline-none ring-navy-700 focus:ring-2" placeholder="Name" />
          <textarea value={props.background} onChange={(event) => props.setBackground(event.target.value)} className="min-h-24 w-full resize-none rounded-md border border-slate-300 px-3 py-2 outline-none ring-navy-700 focus:ring-2" placeholder="Background" />
          <textarea value={props.goals} onChange={(event) => props.setGoals(event.target.value)} className="min-h-24 w-full resize-none rounded-md border border-slate-300 px-3 py-2 outline-none ring-navy-700 focus:ring-2" placeholder="MBA goals" />
          <label className="flex cursor-pointer items-center justify-between gap-4 rounded-md border border-dashed border-slate-300 p-4">
            <span className="inline-flex items-center gap-3 text-sm font-semibold">
              <FileText className="h-5 w-5 text-navy-700" />
              {props.profile?.resume ? "Replace Resume" : "Upload Resume"}
            </span>
            <input type="file" accept=".txt,.pdf" className="hidden" onChange={(event) => props.onUpload(event.target.files?.[0])} />
          </label>
        </div>
        <div className="rounded-md bg-slate-50 p-4">
          <h3 className="font-semibold">{props.profile?.resume?.filename || "No resume stored"}</h3>
          <p className="mt-2 text-sm text-slate-600">{props.profile?.resume ? `Version ${props.profile.resume.version}, parsed ${new Date(props.profile.resume.parsed_at).toLocaleDateString()}` : "Upload once to create the candidate profile."}</p>
          <pre className="mt-4 max-h-80 overflow-auto whitespace-pre-wrap text-xs leading-5 text-slate-600">{props.profile?.resume?.extracted_text || ""}</pre>
        </div>
      </div>
    </section>
  );
}

function HistoryView(props: { history: InterviewHistoryItem[]; onReport: (sessionId: string) => void; onCompare: () => void }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-panel">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="inline-flex items-center gap-2 text-xl font-semibold"><History className="h-5 w-5" /> Past Interviews</h2>
        <button onClick={props.onCompare} disabled={props.history.length < 2} className="rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold disabled:opacity-50">Compare Reports</button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead><tr className="border-b text-left text-slate-500"><th className="py-3">Date</th><th>Score</th><th>Verdict</th><th>Duration</th><th>Type</th><th></th></tr></thead>
          <tbody>
            {props.history.map((item) => (
              <tr key={item.session_id} className="border-b border-slate-100">
                <td className="py-3">{new Date(item.interview_date).toLocaleDateString()}</td>
                <td>{item.overall_score ?? "N/A"}</td>
                <td>{item.verdict ?? item.status}</td>
                <td>{Math.round(item.duration_seconds / 60)} min</td>
                <td>{item.interview_type}</td>
                <td className="text-right"><button onClick={() => props.onReport(item.session_id)} className="rounded-md border border-slate-300 px-3 py-2 font-semibold">View Report</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ProgressView({ progress }: { progress: ProgressDashboardResponse | null }) {
  const latest = progress?.points.at(-1);
  const metrics = latest
    ? [
        ["Communication", latest.communication],
        ["Leadership", latest.leadership],
        ["Business Awareness", latest.business_awareness],
        ["MBA Fit", latest.mba_fit],
        ["Career Clarity", latest.career_clarity],
        ["Academic Depth", latest.academic_depth]
      ]
    : [];
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-panel">
      <h2 className="inline-flex items-center gap-2 text-xl font-semibold"><BarChart3 className="h-5 w-5" /> Progress Dashboard</h2>
      <p className="mt-3 text-sm leading-6 text-slate-600">{progress?.latest.growth_summary || "No progress snapshots yet."}</p>
      <div className="mt-5 grid gap-3 md:grid-cols-3">
        {metrics.map(([label, value]) => <Metric key={label as string} label={label as string} value={typeof value === "number" ? value.toFixed(1) : "N/A"} />)}
      </div>
      <ListBlock title="Improved Areas" items={progress?.latest.improved_areas || []} />
      <ListBlock title="Recurring Weaknesses" items={progress?.latest.recurring_weaknesses || []} />
      <ListBlock title="Next Focus Areas" items={progress?.latest.next_focus_areas || []} />
    </section>
  );
}

function ComparisonView({ comparison }: { comparison: ReportComparisonResponse }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-panel">
      <h2 className="text-xl font-semibold">Report Comparison</h2>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <Metric label="Earlier Attempt" value={`${comparison.left.overall_score}/10`} />
        <Metric label="Later Attempt" value={`${comparison.right.overall_score}/10`} />
      </div>
      <ListBlock title="Score Changes" items={comparison.score_changes} />
      <ListBlock title="Improved Areas" items={comparison.improved_areas} />
      <ListBlock title="Remaining Weaknesses" items={comparison.remaining_weaknesses} />
      <ListBlock title="Panel Observations" items={comparison.panel_observations} />
    </section>
  );
}

function ReportView({ report }: { report: InterviewReport }) {
  const [practiced, setPracticed] = useState<string | null>(null);
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-panel">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-navy-700">Panel Report</p>
          <h2 className="text-2xl font-semibold">{report.verdict}</h2>
        </div>
        <a href={apiUrl(`/sessions/${report.session_id}/report.pdf`)} className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold">
          <Download className="h-4 w-4" />
          Download PDF
        </a>
      </div>
      <Metric label="Overall Score" value={`${report.overall_score}/10`} />
      <p className="mt-5 leading-7 text-slate-700">{report.executive_summary}</p>
      <p className="mt-4 rounded-md bg-slate-50 p-4 text-sm leading-6 text-slate-700">{report.mba_readiness_assessment}</p>
      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <ListBlock title="Strengths" items={report.strengths} />
        <ListBlock title="Weaknesses" items={report.weaknesses} />
        <ListBlock title="Panel Concerns" items={report.panel_concerns} />
        <ListBlock title="Transcript Evidence" items={report.transcript_evidence.map((item) => `${item.topic}: ${item.evidence}`)} />
      </div>
      <h3 className="mt-6 font-semibold">Follow-up Coaching</h3>
      <div className="mt-3 grid gap-3">
        {report.coaching_items.map((item) => (
          <div key={item.question} className="rounded-md border border-slate-200 p-4">
            <p className="font-semibold">{item.question}</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">{item.why_panel_would_ask}</p>
            <p className="mt-2 text-sm leading-6 text-slate-700">{item.ideal_answer}</p>
            <button
              onClick={async () => {
                if (item.practice_id) {
                  const response = await practiceAgain(item.practice_id);
                  setPracticed(`${response.question} practiced ${response.practiced_count} time(s).`);
                }
              }}
              className="mt-3 inline-flex items-center gap-2 rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold"
            >
              <RefreshCw className="h-4 w-4" />
              Practice Again
            </button>
          </div>
        ))}
      </div>
      {practiced ? <p className="mt-3 text-sm font-medium text-navy-700">{practiced}</p> : null}
      <ListBlock title="Interview Preparedness Benchmark" items={report.benchmarking.map((item) => `${item.category}: Communication ${item.communication}, Leadership ${item.leadership}, Business ${item.business_awareness}, Academic ${item.academic_depth}, MBA Fit ${item.mba_fit}`)} />
      <p className="mt-2 text-xs text-slate-500">{report.benchmark_disclaimer}</p>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-2 text-xl font-semibold text-navy-900">{value}</p>
    </div>
  );
}

function ListBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="mt-5">
      <h3 className="font-semibold">{title}</h3>
      <ul className="mt-2 space-y-2 text-sm leading-6 text-slate-600">
        {(items.length ? items : ["No items yet."]).map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  );
}
