"use client";

import { useEffect, useState } from "react";
import {
  BarChart3,
  ArrowLeft,
  FileText,
  History,
  Loader2,
  LogOut,
  Play,
  RefreshCw,
  Trash2,
  User,
  BookOpen,
  TrendingUp,
  GitCompare,
  AlertCircle,
  CheckCircle2,
  Clock,
  ChevronRight,
} from "lucide-react";
import type { Session } from "@supabase/supabase-js";
import { InterviewRoom } from "@/components/InterviewRoom";
import { ScoreBadge, ScoreRing } from "@/components/ScoreBadge";
import { DimensionGrid } from "@/components/DimensionGrid";
import { BenchmarkTable } from "@/components/BenchmarkTable";
import { ScoreChart, MiniScoreChart } from "@/components/ScoreChart";
import { CoachingCard } from "@/components/CoachingCard";
import { ReportDownloadButton } from "@/components/ReportDownloadButton";
import {
  compareReports,
  createSession,
  deleteResume,
  deleteSession,
  getHistory,
  getMe,
  getProgress,
  getReport,
  uploadResume,
} from "@/lib/api";
import { supabase } from "@/lib/supabase";
import type {
  InterviewHistoryItem,
  InterviewReport,
  ProgressDashboardResponse,
  ReportComparisonResponse,
  SessionResponse,
  UserProfileResponse,
} from "@/lib/types";

const DEMO_EMAIL = process.env.NEXT_PUBLIC_DEMO_EMAIL ?? "demo@paneliq.local";
const DEMO_PASSWORD = process.env.NEXT_PUBLIC_DEMO_PASSWORD ?? "demo1234";

type View = "dashboard" | "resume" | "history" | "progress" | "compare" | "report";

const NAV_ITEMS: { id: View; label: string; icon: React.ReactNode }[] = [
  { id: "dashboard", label: "Dashboard", icon: <BarChart3 className="h-4 w-4" /> },
  { id: "resume",    label: "Resume",    icon: <FileText className="h-4 w-4" /> },
  { id: "history",   label: "History",   icon: <History className="h-4 w-4" /> },
  { id: "progress",  label: "Progress",  icon: <TrendingUp className="h-4 w-4" /> },
];

export default function Home() {
  const [deletingSession, setDeletingSession] = useState<string | null>(null);
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
  const completedHistory = history.filter(
    (item) => item.status === "completed" && item.overall_score !== null
  );

  useEffect(() => {
    if (!supabase) return;
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) =>
      setSession(nextSession)
    );
    return () => data.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (signedIn && !activeSession) refreshApp();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signedIn, activeSession]);

  async function refreshApp(isRetry = false) {
    setLoading(true);
    if (!isRetry) setError("");
    try {
      const [meResult, pastResult, trendResult] = await Promise.allSettled([
        getMe(), getHistory(), getProgress()
      ]);

      if (meResult.status === "fulfilled") {
        const me = meResult.value;
        setProfile(me);
        if (me.profile) {
          setName((me.profile as { name?: string }).name ?? "");
          setBackground((me.profile as { background?: string }).background ?? "");
          setGoals((me.profile as { goals?: string }).goals ?? "");
        } else if (me.user.full_name) {
          setName(me.user.full_name);
        }
      } else {
        const err = meResult.reason;
        const isNetwork = err instanceof TypeError && err.message === "Failed to fetch";
        if (isNetwork && !isRetry) {
          setError("Backend unavailable — retrying…");
          setTimeout(() => refreshApp(true), 1500);
          setLoading(false);
          return;
        }
        if (!isRetry) setError(err instanceof Error ? err.message : "Unable to load PANELIQ data.");
      }

      if (pastResult.status === "fulfilled") setHistory(pastResult.value);
      if (trendResult.status === "fulfilled") setProgress(trendResult.value);

      if (isRetry) setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load PANELIQ data.");
    } finally {
      setLoading(false);
    }
  }

  async function loginWithEmail() {
    if (!supabase) { setError("Configure Supabase environment variables."); return; }
    setLoading(true);
    setError("");
    try {
      const normalizedEmail = email.trim().toLowerCase();
      const { error: authError } = await supabase.auth.signInWithPassword({
        email: normalizedEmail, password,
      });
      if (authError) {
        const msg = authError.message.toLowerCase();
        if (!msg.includes("invalid login credentials") && !msg.includes("user not found")) {
          throw authError;
        }
        const { error: signupError } = await supabase.auth.signUp({ email, password });
        if (signupError) throw signupError;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
    } finally {
      setLoading(false);
    }
  }

  async function loginWithGoogle() {
    if (!supabase) { setError("Configure Supabase for Google login."); return; }
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: window.location.origin },
    });
  }

  async function enterDemo() {
    if (!supabase) { setError("Supabase is not configured."); return; }
    setLoading(true);
    setError("");
    try {
      const { error: authError } = await supabase.auth.signInWithPassword({
        email: DEMO_EMAIL, password: DEMO_PASSWORD,
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
    setView("dashboard");
    await supabase?.auth.signOut();
  }

  async function handleResume(file: File | undefined) {
    if (!file) return;
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
      setError("Upload a resume before starting an interview.");
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
        interview_type: "IIM MBA Panel",
      });
      setActiveSession(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create session.");
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
    if (completedHistory.length < 2) return;
    setLoading(true);
    setError("");
    try {
      // Compare the two most recent completed sessions (index 0 = most recent)
      const newer = completedHistory[0];
      const older = completedHistory[1];
      setComparison(await compareReports(older.session_id, newer.session_id));
      setView("compare");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to compare reports.");
    } finally {
      setLoading(false);
    }
  }

  async function handleDeleteSession(sessionId: string) {
    setDeletingSession(sessionId);
    setError("");
    try {
      await deleteSession(sessionId);
      await refreshApp();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete session.");
    } finally {
      setDeletingSession(null);
    }
  }

  function navigateTo(v: View) {
    setView(v);
    setActiveReport(null);
    setComparison(null);
    setError("");
  }

  /* ─── Active interview room ─────────────────────────────────── */
  if (activeSession) {
    return (
      <InterviewRoom
        session={activeSession}
        onExit={() => {
          setActiveSession(null);
          refreshApp();
        }}
      />
    );
  }

  /* ─── Login ─────────────────────────────────────────────────── */
  if (!signedIn) {
    return <LoginPage loading={loading} error={error} email={email} password={password} setEmail={setEmail} setPassword={setPassword} onEmailLogin={loginWithEmail} onGoogleLogin={loginWithGoogle} onDemo={enterDemo} />;
  }

  /* ─── App shell ─────────────────────────────────────────────── */
  const userName = name || profile?.user.full_name || "Candidate";

  return (
    <div className="min-h-screen bg-[#f8fafc] text-slate-900">
      {/* Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-56 flex-col border-r border-slate-200 bg-white lg:flex">
        <div className="flex h-16 items-center border-b border-slate-100 px-5">
          <div>
            <p className="text-xs font-bold tracking-[0.14em] uppercase text-navy-700">PANELIQ</p>
            <p className="text-[11px] text-slate-400">MBA Interview Platform</p>
          </div>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-4">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              onClick={() => navigateTo(item.id)}
              className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                view === item.id
                  ? "bg-navy-900 text-white"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              }`}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </nav>
        <div className="border-t border-slate-100 p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-navy-100">
              <User className="h-4 w-4 text-navy-700" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-slate-800">{userName}</p>
              <p className="truncate text-xs text-slate-400">{profile?.user.email}</p>
            </div>
          </div>
          <button
            onClick={signOut}
            className="mt-3 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-900 transition-colors"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-slate-200 bg-white px-4 lg:hidden">
        <p className="text-sm font-bold tracking-widest uppercase text-navy-700">PANELIQ</p>
        <div className="flex items-center gap-2">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              onClick={() => navigateTo(item.id)}
              className={`rounded-md p-2 ${view === item.id ? "bg-navy-900 text-white" : "text-slate-500"}`}
              title={item.label}
            >
              {item.icon}
            </button>
          ))}
          <button onClick={signOut} className="rounded-md p-2 text-slate-500">
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </header>

      {/* Main content */}
      <main className="lg:pl-56">
        <div className="mx-auto max-w-5xl px-4 py-6 lg:px-8">
          {/* Error banner */}
          {error && (
            <div className="mb-5 flex items-center gap-3 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700 animate-fade-in">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              {error}
              <button onClick={() => setError("")} className="ml-auto text-rose-400 hover:text-rose-600">✕</button>
            </div>
          )}
          {loading && (
            <div className="mb-5 flex items-center gap-2 text-sm text-slate-500">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Loading…
            </div>
          )}

          {/* Back button for sub-views */}
          {(view === "report" || view === "compare") && (
            <button
              onClick={() => navigateTo("history")}
              className="mb-5 flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-900 transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to History
            </button>
          )}

          {view === "dashboard" && (
            <DashboardView
              profile={profile}
              history={history}
              progress={progress}
              loading={loading}
              onStart={beginInterview}
              onReport={openReport}
              onCompare={runComparison}
              onViewHistory={() => navigateTo("history")}
              onViewProgress={() => navigateTo("progress")}
            />
          )}
          {view === "resume" && (
            <ResumeManagerView
              profile={profile}
              name={name}
              background={background}
              goals={goals}
              setName={setName}
              setBackground={setBackground}
              setGoals={setGoals}
              onUpload={handleResume}
              onDelete={removeResume}
              loading={loading}
            />
          )}
          {view === "history" && (
            <HistoryView
              history={history}
              onReport={openReport}
              onCompare={runComparison}
              onDelete={handleDeleteSession}
              deletingSession={deletingSession}
            />
          )}
          {view === "progress" && <ProgressView progress={progress} />}
          {view === "compare" && comparison && (
            <ComparisonView comparison={comparison} />
          )}
          {view === "report" && activeReport && (
            <ReportView report={activeReport} />
          )}
        </div>
      </main>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   LOGIN PAGE
═══════════════════════════════════════════════════════════════ */
function LoginPage(props: {
  loading: boolean; error: string;
  email: string; password: string;
  setEmail: (v: string) => void; setPassword: (v: string) => void;
  onEmailLogin: () => void; onGoogleLogin: () => void; onDemo: () => void;
}) {
  const features = [
    { icon: <BookOpen className="h-4 w-4" />, text: "AI IIM-style panel with 3 distinct interviewers" },
    { icon: <FileText className="h-4 w-4" />, text: "Upload once, reuse resume across all sessions" },
    { icon: <TrendingUp className="h-4 w-4" />, text: "Track 6 dimensions of progress over time" },
    { icon: <GitCompare className="h-4 w-4" />, text: "Compare any two interview reports side-by-side" },
    { icon: <BarChart3 className="h-4 w-4" />, text: "Download evidence-based PDF coaching reports" },
  ];

  return (
    <main className="min-h-screen bg-[#f8fafc]">
      <div className="mx-auto grid max-w-6xl min-h-screen gap-0 lg:grid-cols-[1.1fr_0.9fr]">
        {/* Left — brand */}
        <section className="flex flex-col justify-center px-8 py-16 lg:px-16 animate-fade-in">
          <p className="mb-4 text-xs font-bold uppercase tracking-[0.16em] text-navy-700">PANELIQ</p>
          <h1 className="text-4xl font-bold tracking-tight text-slate-900 leading-tight">
            AI MBA Interview<br />Coaching Platform
          </h1>
          <p className="mt-5 max-w-md text-base leading-7 text-slate-500">
            Practice IIM-style panel interviews, receive structured feedback, and track your improvement — all backed by real data.
          </p>
          <ul className="mt-8 space-y-3.5">
            {features.map((f, i) => (
              <li
                key={i}
                className="flex items-center gap-3 text-sm text-slate-600 animate-slide-up"
                style={{ animationDelay: `${i * 60}ms` }}
              >
                <span className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-navy-100 text-navy-700">
                  {f.icon}
                </span>
                {f.text}
              </li>
            ))}
          </ul>
          <div className="mt-10">
            <button
              onClick={props.onDemo}
              disabled={props.loading}
              className="btn btn-primary px-5 py-2.5 text-sm"
            >
              {props.loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              {props.loading ? "Signing in…" : "Try Demo Account"}
            </button>
            <p className="mt-2 text-xs text-slate-400">
              Pre-seeded profile with 3 completed interview sessions.
            </p>
          </div>
        </section>

        {/* Right — sign in card */}
        <section className="flex items-center justify-center px-8 py-16 lg:border-l lg:border-slate-200 animate-fade-in" style={{ animationDelay: "0.1s" }}>
          <div className="w-full max-w-sm">
            <div className="card p-7">
              <h2 className="text-xl font-semibold text-slate-900">Sign in</h2>
              <p className="mt-1 text-sm text-slate-500">New users are registered automatically.</p>
              <div className="mt-6 space-y-3">
                <input
                  id="email"
                  type="email"
                  value={props.email}
                  onChange={(e) => props.setEmail(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && props.onEmailLogin()}
                  placeholder="Email address"
                  className="w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm outline-none transition-colors placeholder:text-slate-400 focus:border-navy-700 focus:ring-2 focus:ring-navy-200"
                />
                <input
                  id="password"
                  type="password"
                  value={props.password}
                  onChange={(e) => props.setPassword(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && props.onEmailLogin()}
                  placeholder="Password"
                  className="w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm outline-none transition-colors placeholder:text-slate-400 focus:border-navy-700 focus:ring-2 focus:ring-navy-200"
                />
                <button
                  id="email-login-btn"
                  onClick={props.onEmailLogin}
                  disabled={props.loading || !props.email || !props.password}
                  className="btn btn-primary w-full justify-center py-2.5"
                >
                  {props.loading ? "Working…" : "Continue with Email"}
                </button>
                <div className="relative flex items-center gap-3">
                  <div className="flex-1 border-t border-slate-200" />
                  <span className="text-xs text-slate-400">or</span>
                  <div className="flex-1 border-t border-slate-200" />
                </div>
                <button
                  id="google-login-btn"
                  onClick={props.onGoogleLogin}
                  className="btn btn-secondary w-full justify-center py-2.5"
                >
                  <svg className="h-4 w-4" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M23.745 12.27c0-.79-.07-1.54-.19-2.27h-11.3v4.51h6.47c-.29 1.48-1.14 2.73-2.4 3.58v3h3.86c2.26-2.09 3.56-5.17 3.56-8.82z"/>
                    <path fill="#34A853" d="M12.255 24c3.24 0 5.95-1.08 7.93-2.91l-3.86-3c-1.08.72-2.45 1.16-4.07 1.16-3.13 0-5.78-2.11-6.73-4.96h-3.98v3.09C3.515 21.3 7.615 24 12.255 24z"/>
                    <path fill="#FBBC05" d="M5.525 14.29c-.25-.72-.38-1.49-.38-2.29s.14-1.57.38-2.29V6.62h-3.98a11.86 11.86 0 0 0 0 10.76l3.98-3.09z"/>
                    <path fill="#EA4335" d="M12.255 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C18.205 1.19 15.495 0 12.255 0c-4.64 0-8.74 2.7-10.71 6.62l3.98 3.09c.95-2.85 3.6-4.96 6.73-4.96z"/>
                  </svg>
                  Continue with Google
                </button>
              </div>
              {props.error && (
                <p className="mt-4 flex items-center gap-2 text-sm text-rose-600">
                  <AlertCircle className="h-3.5 w-3.5" />
                  {props.error}
                </p>
              )}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

/* ═══════════════════════════════════════════════════════════════
   DASHBOARD VIEW
═══════════════════════════════════════════════════════════════ */
function DashboardView(props: {
  profile: UserProfileResponse | null;
  history: InterviewHistoryItem[];
  progress: ProgressDashboardResponse | null;
  loading: boolean;
  onStart: () => void;
  onReport: (sessionId: string) => void;
  onCompare: () => void;
  onViewHistory: () => void;
  onViewProgress: () => void;
}) {
  const latest = props.history.find((h) => h.status === "completed" && h.overall_score !== null);
  const attempts = props.history.length;
  const hasResume = Boolean(props.profile?.resume);
  const hasProgress = (props.progress?.points.length ?? 0) >= 2;

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Page title */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500">
          {hasResume
            ? `Resume: ${props.profile?.resume?.filename} · v${props.profile?.resume?.version}`
            : "No resume uploaded — add one to start your first interview."}
        </p>
      </div>

      {/* Top metrics row */}
      <div className="grid gap-4 sm:grid-cols-3">
        <MetricCard
          label="Latest Score"
          value={latest?.overall_score !== undefined && latest?.overall_score !== null ? `${latest.overall_score.toFixed(1)}/10` : "—"}
          sub={latest?.verdict ?? "No completed sessions yet"}
          accent={latest?.overall_score !== undefined && latest?.overall_score !== null ? (latest.overall_score >= 8 ? "green" : latest.overall_score >= 6.5 ? "navy" : "amber") : "neutral"}
        />
        <MetricCard
          label="Total Sessions"
          value={String(attempts)}
          sub={attempts === 1 ? "interview attempt" : "interview attempts"}
          accent="neutral"
        />
        <MetricCard
          label="Resume Version"
          value={props.profile?.resume ? `v${props.profile.resume.version}` : "—"}
          sub={props.profile?.resume ? `Uploaded ${new Date(props.profile.resume.parsed_at).toLocaleDateString("en-IN")}` : "Upload to enable interviews"}
          accent="neutral"
        />
      </div>

      {/* Main cards row */}
      <div className="grid gap-5 lg:grid-cols-2">
        {/* Start interview */}
        <div className="card p-6">
          <h2 className="text-base font-semibold text-slate-900">Ready to Practice?</h2>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            {hasResume
              ? "Your resume is loaded. Start an IIM-style panel interview with 3 AI interviewers."
              : "Upload a resume first — it's stored once and reused across all sessions."}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              onClick={props.onStart}
              disabled={props.loading || !hasResume}
              className="btn btn-primary py-2"
            >
              <Play className="h-3.5 w-3.5" />
              Start Interview
            </button>
            {latest && (
              <button onClick={() => props.onReport(latest.session_id)} className="btn btn-secondary py-2">
                View Latest Report
              </button>
            )}
            {props.history.length >= 2 && (
              <button onClick={props.onCompare} className="btn btn-secondary py-2">
                <GitCompare className="h-3.5 w-3.5" />
                Compare Reports
              </button>
            )}
          </div>
        </div>

        {/* Growth summary */}
        <div className="card p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-900">Growth Summary</h2>
            {hasProgress && (
              <button onClick={props.onViewProgress} className="text-xs font-medium text-navy-700 hover:underline">
                Full progress →
              </button>
            )}
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            {props.progress?.latest.growth_summary || "Complete interviews to build progress intelligence."}
          </p>
          {hasProgress && props.progress && (
            <div className="mt-3">
              <MiniScoreChart points={props.progress.points} />
            </div>
          )}
          {props.progress?.latest.next_focus_areas?.length ? (
            <div className="mt-3">
              <p className="text-label mb-2">Focus areas</p>
              <div className="flex flex-wrap gap-1.5">
                {props.progress.latest.next_focus_areas.slice(0, 3).map((area) => (
                  <span key={area} className="rounded-full bg-navy-100 px-2.5 py-0.5 text-xs font-medium text-navy-800">
                    {area}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </div>

      {/* Recent history */}
      {props.history.length > 0 && (
        <div className="card p-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-900">Recent Sessions</h2>
            <button onClick={props.onViewHistory} className="text-xs font-medium text-navy-700 hover:underline">
              All sessions →
            </button>
          </div>
          <div className="space-y-2">
            {props.history.slice(0, 4).map((item) => (
              <div key={item.session_id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-100 px-3 py-2.5">
                <div className="flex items-center gap-3 min-w-0">
                  <div className={`h-2 w-2 flex-shrink-0 rounded-full ${item.status === "completed" ? "bg-emerald-500" : "bg-amber-400"}`} />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-800">
                      {new Date(item.interview_date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
                    </p>
                    <p className="text-xs text-slate-400">
                      {Math.round(item.duration_seconds / 60)} min · {item.interview_type}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {item.overall_score !== null && (
                    <span className="text-sm font-semibold text-slate-700">{item.overall_score.toFixed(1)}</span>
                  )}
                  {item.verdict && <ScoreBadge verdict={item.verdict} size="sm" />}
                  {item.status === "completed" && (
                    <button
                      onClick={() => props.onReport(item.session_id)}
                      className="rounded-md border border-slate-200 p-1.5 text-slate-400 hover:text-navy-700 hover:border-navy-300 transition-colors"
                    >
                      <ChevronRight className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   RESUME MANAGER
═══════════════════════════════════════════════════════════════ */
function ResumeManagerView(props: {
  profile: UserProfileResponse | null;
  name: string; background: string; goals: string;
  setName: (v: string) => void; setBackground: (v: string) => void; setGoals: (v: string) => void;
  onUpload: (f: File | undefined) => void; onDelete: () => void; loading: boolean;
}) {
  const resume = props.profile?.resume;

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Resume Profile</h1>
          <p className="mt-1 text-sm text-slate-500">
            Upload once. Your resume persists across all interview sessions.
          </p>
        </div>
        {resume && (
          <button onClick={props.onDelete} disabled={props.loading} className="btn btn-danger flex-shrink-0">
            <Trash2 className="h-3.5 w-3.5" />
            Delete Resume
          </button>
        )}
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
        {/* Form */}
        <div className="card p-6 space-y-4">
          <h2 className="text-base font-semibold text-slate-900">Candidate Information</h2>
          <div className="space-y-3">
            <div>
              <label className="text-label block mb-1.5">Full name</label>
              <input
                value={props.name}
                onChange={(e) => props.setName(e.target.value)}
                placeholder="Your name"
                className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm outline-none focus:border-navy-700 focus:ring-2 focus:ring-navy-200"
              />
            </div>
            <div>
              <label className="text-label block mb-1.5">Background</label>
              <textarea
                value={props.background}
                onChange={(e) => props.setBackground(e.target.value)}
                placeholder="e.g. Final-year engineering student with internships and leadership roles"
                rows={3}
                className="w-full resize-none rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm outline-none focus:border-navy-700 focus:ring-2 focus:ring-navy-200"
              />
            </div>
            <div>
              <label className="text-label block mb-1.5">MBA goals</label>
              <textarea
                value={props.goals}
                onChange={(e) => props.setGoals(e.target.value)}
                placeholder="e.g. Product management after an MBA with a consumer technology focus"
                rows={3}
                className="w-full resize-none rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm outline-none focus:border-navy-700 focus:ring-2 focus:ring-navy-200"
              />
            </div>
            <label className="flex cursor-pointer items-center justify-between gap-4 rounded-xl border-2 border-dashed border-slate-300 p-4 hover:border-navy-400 transition-colors">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-navy-100">
                  <FileText className="h-5 w-5 text-navy-700" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-800">
                    {resume ? "Replace Resume" : "Upload Resume"}
                  </p>
                  <p className="text-xs text-slate-400">PDF or TXT file</p>
                </div>
              </div>
              <input
                type="file"
                accept=".txt,.pdf"
                className="hidden"
                onChange={(e) => props.onUpload(e.target.files?.[0])}
              />
              <span className="btn btn-secondary text-xs px-3 py-1.5 pointer-events-none">
                Browse
              </span>
            </label>
          </div>
        </div>

        {/* Resume preview */}
        <div className="card p-6">
          {resume ? (
            <>
              <div className="mb-3 flex items-start gap-3">
                <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-emerald-100">
                  <CheckCircle2 className="h-4.5 w-4.5 text-emerald-700" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-900">{resume.filename}</p>
                  <p className="text-xs text-slate-400">
                    Version {resume.version} · Parsed {new Date(resume.parsed_at).toLocaleDateString("en-IN")}
                  </p>
                </div>
              </div>
              <div className="rounded-lg bg-slate-50 p-4">
                <p className="text-label mb-2">Extracted text</p>
                <pre className="max-h-72 overflow-auto whitespace-pre-wrap text-xs leading-5 text-slate-600">
                  {resume.extracted_text || "No text extracted."}
                </pre>
              </div>
            </>
          ) : (
            <div className="flex h-full flex-col items-center justify-center text-center py-8">
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100">
                <FileText className="h-6 w-6 text-slate-400" />
              </div>
              <p className="text-sm font-medium text-slate-600">No resume stored</p>
              <p className="mt-1 text-xs text-slate-400">Upload a PDF or TXT file to get started.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   HISTORY VIEW
═══════════════════════════════════════════════════════════════ */
function HistoryView(props: {
  history: InterviewHistoryItem[];
  onReport: (sessionId: string) => void;
  onCompare: () => void;
  onDelete: (sessionId: string) => void;
  deletingSession: string | null;
}) {
  const completedCount = props.history.filter((h) => h.status === "completed").length;

  if (!props.history.length) {
    return (
      <div className="space-y-5 animate-fade-in">
        <h1 className="text-2xl font-bold text-slate-900">Interview History</h1>
        <div className="card p-10 text-center">
          <History className="mx-auto mb-3 h-10 w-10 text-slate-300" />
          <p className="text-sm font-medium text-slate-500">No interviews yet.</p>
          <p className="mt-1 text-xs text-slate-400">Complete a session to see it here.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Interview History</h1>
          {completedCount >= 2 && (
            <p className="mt-0.5 text-xs text-slate-400">
              Comparing your 2 most recent completed sessions
            </p>
          )}
        </div>
        <button
          onClick={props.onCompare}
          disabled={completedCount < 2}
          className="btn btn-secondary"
          title={completedCount < 2 ? "Complete at least 2 sessions to compare" : "Compare 2 most recent sessions"}
        >
          <GitCompare className="h-3.5 w-3.5" />
          Compare Last 2
        </button>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-left">
                <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Date</th>
                <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Score</th>
                <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Verdict</th>
                <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Duration</th>
                <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Status</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody>
              {props.history.map((item, idx) => {
                const isIncomplete = item.status !== "completed";
                const isDeleting = props.deletingSession === item.session_id;
                return (
                  <tr
                    key={item.session_id}
                    className={`border-b border-slate-100 last:border-0 transition-colors animate-slide-up ${
                      isIncomplete ? "bg-slate-50/60 opacity-75" : "hover:bg-slate-50/50"
                    }`}
                    style={{ animationDelay: `${idx * 40}ms` }}
                  >
                    <td className="px-5 py-3.5">
                      <p className="font-medium text-slate-800">
                        {new Date(item.interview_date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
                      </p>
                      <p className="text-xs text-slate-400">{item.interview_type}</p>
                    </td>
                    <td className="px-5 py-3.5">
                      {item.overall_score !== null ? (
                        <span className={`font-bold tabular-nums ${
                          item.overall_score >= 8 ? "text-emerald-700" :
                          item.overall_score >= 7 ? "text-navy-700" :
                          item.overall_score >= 5.5 ? "text-amber-600" : "text-rose-700"
                        }`}>
                          {item.overall_score.toFixed(1)}
                          <span className="font-normal text-slate-400">/10</span>
                        </span>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="px-5 py-3.5">
                      {item.verdict
                        ? <ScoreBadge verdict={item.verdict} size="sm" />
                        : <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-500">Incomplete</span>
                      }
                    </td>
                    <td className="px-5 py-3.5 text-slate-500">
                      <span className="flex items-center gap-1.5">
                        <Clock className="h-3.5 w-3.5 text-slate-400" />
                        {item.duration_seconds > 0 ? `${Math.round(item.duration_seconds / 60)} min` : "—"}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${
                        item.status === "completed" ? "text-emerald-700" :
                        item.status === "in_progress" ? "text-amber-700" : "text-slate-400"
                      }`}>
                        <span className={`h-1.5 w-1.5 rounded-full ${
                          item.status === "completed" ? "bg-emerald-500" :
                          item.status === "in_progress" ? "bg-amber-400" : "bg-slate-300"
                        }`} />
                        {item.status === "completed" ? "Completed" :
                         item.status === "in_progress" ? "In Progress" : "Not started"}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {item.status === "completed" && (
                          <button
                            onClick={() => props.onReport(item.session_id)}
                            className="btn btn-secondary text-xs px-3 py-1.5"
                          >
                            View Report
                          </button>
                        )}
                        {isIncomplete && (
                          <button
                            onClick={() => props.onDelete(item.session_id)}
                            disabled={isDeleting}
                            title="Delete incomplete session"
                            className="flex items-center gap-1 rounded-md border border-rose-200 px-2.5 py-1.5 text-xs font-medium text-rose-600 hover:bg-rose-50 transition-colors disabled:opacity-50"
                          >
                            {isDeleting
                              ? <Loader2 className="h-3 w-3 animate-spin" />
                              : <Trash2 className="h-3 w-3" />
                            }
                            Delete
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   PROGRESS VIEW
═══════════════════════════════════════════════════════════════ */
function ProgressView({ progress }: { progress: ProgressDashboardResponse | null }) {
  const latest = progress?.points.at(-1);

  const metrics = latest
    ? [
        { label: "Communication",      value: latest.communication },
        { label: "Leadership",         value: latest.leadership },
        { label: "Business Awareness", value: latest.business_awareness },
        { label: "MBA Fit",            value: latest.mba_fit },
        { label: "Career Clarity",     value: latest.career_clarity },
        { label: "Academic Depth",     value: latest.academic_depth },
      ]
    : [];

  return (
    <div className="space-y-5 animate-fade-in">
      <h1 className="text-2xl font-bold text-slate-900">Progress Dashboard</h1>

      {/* Chart */}
      <div className="card p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-900">Score Trajectory</h2>
          <span className="text-xs text-slate-400">{progress?.points.length ?? 0} data point{progress?.points.length !== 1 ? "s" : ""}</span>
        </div>
        <ScoreChart points={progress?.points ?? []} />
      </div>

      {/* Latest snapshot metrics */}
      {metrics.length > 0 && (
        <div className="card p-6">
          <h2 className="mb-4 text-base font-semibold text-slate-900">Latest Snapshot</h2>
          <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
            {metrics.map(({ label, value }) => (
              <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-label mb-2">{label}</p>
                {value !== null && value !== undefined ? (
                  <>
                    <p className={`text-2xl font-bold tabular-nums ${
                      value >= 8 ? "text-emerald-700" : value >= 7 ? "text-navy-700" : value >= 5.5 ? "text-amber-700" : "text-rose-700"
                    }`}>
                      {value.toFixed(1)}
                    </p>
                    <div className="mt-2 progress-bar-track">
                      <div className={`progress-bar-fill ${value >= 8 ? "bg-emerald-600" : value >= 7 ? "bg-navy-700" : value >= 5.5 ? "bg-amber-500" : "bg-rose-600"}`}
                           style={{ width: `${(value / 10) * 100}%` }} />
                    </div>
                  </>
                ) : (
                  <p className="text-xl font-bold text-slate-300">—</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Analysis cards */}
      {progress?.latest && (
        <div className="grid gap-4 md:grid-cols-3">
          <AnalysisCard title="Improved Areas" items={progress.latest.improved_areas} colour="emerald" icon={<CheckCircle2 className="h-4 w-4" />} />
          <AnalysisCard title="Recurring Weaknesses" items={progress.latest.recurring_weaknesses} colour="rose" icon={<AlertCircle className="h-4 w-4" />} />
          <AnalysisCard title="Next Focus Areas" items={progress.latest.next_focus_areas} colour="navy" icon={<TrendingUp className="h-4 w-4" />} />
        </div>
      )}

      {progress?.latest.growth_summary && (
        <div className="card px-5 py-4">
          <p className="text-label mb-2">Growth Summary</p>
          <p className="text-sm leading-6 text-slate-700">{progress.latest.growth_summary}</p>
        </div>
      )}
    </div>
  );
}

function AnalysisCard({ title, items, colour, icon }: { title: string; items: string[]; colour: "emerald" | "rose" | "navy"; icon: React.ReactNode }) {
  const colours = {
    emerald: { bg: "bg-emerald-50", icon: "text-emerald-700 bg-emerald-100", text: "text-emerald-800", chip: "bg-emerald-50 text-emerald-800" },
    rose: { bg: "bg-rose-50", icon: "text-rose-700 bg-rose-100", text: "text-rose-800", chip: "bg-rose-50 text-rose-800" },
    navy: { bg: "bg-navy-50", icon: "text-navy-700 bg-navy-100", text: "text-navy-800", chip: "bg-navy-50 text-navy-800" },
  }[colour];

  return (
    <div className="card p-4">
      <div className="mb-3 flex items-center gap-2.5">
        <span className={`flex h-7 w-7 items-center justify-center rounded-lg ${colours.icon}`}>
          {icon}
        </span>
        <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
      </div>
      {items.length ? (
        <ul className="space-y-1.5">
          {items.map((item) => (
            <li key={item} className={`rounded-md px-2.5 py-1.5 text-xs leading-5 ${colours.chip}`}>
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-slate-400 italic">None recorded yet.</p>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   COMPARISON VIEW
═══════════════════════════════════════════════════════════════ */
function ComparisonView({ comparison }: { comparison: ReportComparisonResponse }) {
  const { left, right, score_changes, improved_areas, remaining_weaknesses, regressions, panel_observations, benchmark_gaps } = comparison;
  const delta = right.overall_score - left.overall_score;

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Report Comparison</h1>
        <p className="mt-1 text-sm text-slate-500">Previous session vs. most recent session, with IIM benchmark analysis.</p>
      </div>

      {/* Score headers — previous vs latest */}
      <div className="grid gap-4 sm:grid-cols-2">
        {[
          { label: "Previous Session", report: left,  sub: "Earlier attempt" },
          { label: "Latest Session",   report: right, sub: "Most recent attempt" },
        ].map(({ label, report, sub }) => (
          <div key={label} className="card p-5 flex items-center gap-5">
            <ScoreRing score={report.overall_score} size={80} />
            <div>
              <p className="text-label mb-0.5">{label}</p>
              <p className="text-xs text-slate-400 mb-2">{sub}</p>
              <ScoreBadge verdict={report.verdict} size="md" />
            </div>
          </div>
        ))}
      </div>

      {/* Delta indicator */}
      <div className={`card px-5 py-4 flex items-center gap-4 ${
        delta > 0 ? "border-emerald-200 bg-emerald-50" :
        delta < 0 ? "border-rose-200 bg-rose-50" : "border-slate-200 bg-slate-50"
      }`}>
        <span className={`text-3xl font-bold tabular-nums ${
          delta > 0 ? "text-emerald-700" : delta < 0 ? "text-rose-700" : "text-slate-500"
        }`}>
          {delta > 0 ? "+" : ""}{delta.toFixed(1)}
        </span>
        <div>
          <p className={`text-sm font-semibold ${
            delta > 0 ? "text-emerald-800" : delta < 0 ? "text-rose-800" : "text-slate-600"
          }`}>
            {delta > 0 ? "Score improved" : delta < 0 ? "Score declined" : "Score unchanged"} between these two sessions
          </p>
          <p className="text-xs text-slate-500 mt-0.5">
            {left.overall_score.toFixed(1)} → {right.overall_score.toFixed(1)} out of 10
          </p>
        </div>
      </div>

      {/* Improved / Weaknesses / Regressions */}
      <div className="grid gap-4 md:grid-cols-3">
        <AnalysisCard title="Improved Areas" items={improved_areas} colour="emerald" icon={<CheckCircle2 className="h-4 w-4" />} />
        <AnalysisCard title="Remaining Weaknesses" items={remaining_weaknesses} colour="rose" icon={<AlertCircle className="h-4 w-4" />} />
        <AnalysisCard title="Regressions" items={regressions ?? []} colour="rose" icon={<TrendingUp className="h-4 w-4 rotate-180" />} />
      </div>

      {/* Dimension score changes */}
      {score_changes.length > 0 && (
        <div className="card p-5">
          <h2 className="mb-3 text-base font-semibold text-slate-900">Dimension Score Changes</h2>
          <ul className="divide-y divide-slate-100">
            {score_changes.map((change) => {
              const hasArrow = change.includes("→");
              const isPositive = hasArrow && change.includes("(+");
              const isNegative = hasArrow && change.includes("(-");
              return (
                <li key={change} className="flex items-center gap-3 py-2.5 text-sm">
                  <span className={`h-2 w-2 flex-shrink-0 rounded-full ${
                    isPositive ? "bg-emerald-500" : isNegative ? "bg-rose-500" : "bg-slate-400"
                  }`} />
                  <span className="text-slate-700">{change}</span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {/* IIM Benchmark Gap Analysis */}
      {benchmark_gaps && benchmark_gaps.length > 0 && (
        <div className="card p-6">
          <div className="mb-5">
            <h2 className="text-base font-semibold text-slate-900">IIM Benchmark Comparison</h2>
            <p className="mt-1 text-xs text-slate-500">
              Your most recent session scores vs. what each IIM profile typically achieves.
              Gap = your score minus the midpoint of the reference range.
            </p>
          </div>
          <div className="space-y-5">
            {benchmark_gaps.map((profile) => (
              <div key={profile.profile} className="rounded-xl border border-slate-200 overflow-hidden">
                <div className={`px-4 py-2.5 border-b border-slate-100 ${
                  profile.profile === "Strong IIM ABC Candidate" ? "bg-emerald-50" :
                  profile.profile === "Typical IIM Convert Candidate" ? "bg-navy-50" : "bg-stone-50"
                }`}>
                  <p className={`text-xs font-bold uppercase tracking-wide ${
                    profile.profile === "Strong IIM ABC Candidate" ? "text-emerald-700" :
                    profile.profile === "Typical IIM Convert Candidate" ? "text-navy-700" : "text-stone-600"
                  }`}>{profile.profile}</p>
                </div>
                <div className="divide-y divide-slate-100">
                  {profile.dimensions.map((dim) => (
                    <div key={dim.dimension} className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-4 px-4 py-3">
                      <p className="text-sm text-slate-700">{dim.dimension}</p>
                      <p className="text-xs text-slate-400 tabular-nums">Ref: {dim.ref_range}</p>
                      <p className="text-sm font-semibold tabular-nums text-slate-800">{dim.your_score.toFixed(1)}</p>
                      <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold tabular-nums ${
                        dim.status === "above" ? "bg-emerald-100 text-emerald-700" :
                        dim.status === "below" ? "bg-rose-100 text-rose-700" : "bg-slate-100 text-slate-600"
                      }`}>
                        {dim.gap > 0 ? "+" : ""}{dim.gap.toFixed(1)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <p className="mt-4 text-xs text-slate-400 italic">
            Benchmark comparisons are interview-readiness indicators only, not admission predictions.
          </p>
        </div>
      )}

      {/* Panel observations */}
      {panel_observations.length > 0 && (
        <div className="card p-5">
          <h2 className="mb-3 text-base font-semibold text-slate-900">Panel Observations</h2>
          <ul className="space-y-2">
            {panel_observations.map((obs) => (
              <li key={obs} className="flex items-start gap-2 text-sm text-slate-600">
                <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-navy-400" />
                {obs}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   REPORT VIEW
═══════════════════════════════════════════════════════════════ */
function ReportView({ report }: { report: InterviewReport }) {
  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-label mb-1">Panel Report</p>
          <h1 className="text-2xl font-bold text-slate-900">Interview Evaluation</h1>
        </div>
        <ReportDownloadButton sessionId={report.session_id} />
      </div>

      {/* Score hero */}
      <div className="card p-6 flex flex-wrap items-center gap-6">
        <ScoreRing score={report.overall_score} size={96} />
        <div className="flex-1 min-w-0">
          <ScoreBadge verdict={report.verdict} size="lg" />
          <p className="mt-3 text-sm leading-6 text-slate-600 max-w-xl">{report.executive_summary || report.feedback_to_candidate}</p>
        </div>
      </div>

      {/* MBA Readiness Assessment */}
      {report.mba_readiness_assessment && (
        <div className="card p-5 border-navy-200 bg-navy-50">
          <p className="text-label mb-2 text-navy-600">MBA Readiness Assessment</p>
          <p className="text-sm leading-6 text-navy-900">{report.mba_readiness_assessment}</p>
        </div>
      )}

      {/* Strengths / Weaknesses / Panel Concerns */}
      <div className="grid gap-4 md:grid-cols-3">
        <ListCard title="Strengths" items={report.strengths} colour="emerald" />
        <ListCard title="Weaknesses" items={report.weaknesses} colour="rose" />
        <ListCard title="Panel Concerns" items={report.panel_concerns} colour="amber" />
      </div>

      {/* Dimension Scores */}
      {report.dimensions?.length > 0 && (
        <div>
          <h2 className="mb-3 text-base font-semibold text-slate-900">Dimension Scores</h2>
          <DimensionGrid dimensions={report.dimensions} />
        </div>
      )}

      {/* Transcript Evidence */}
      {report.transcript_evidence?.length > 0 && (
        <div className="card p-6">
          <h2 className="mb-4 text-base font-semibold text-slate-900">Transcript Evidence</h2>
          <div className="space-y-3">
            {report.transcript_evidence.map((item, idx) => (
              <div key={idx} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="rounded-full bg-navy-100 px-2.5 py-0.5 text-xs font-semibold text-navy-700">
                    {item.topic}
                  </span>
                </div>
                <p className="text-sm text-slate-700 leading-6">
                  <span className="font-medium">Evidence: </span>{item.evidence}
                </p>
                {item.panel_interpretation && (
                  <p className="mt-1.5 text-xs text-slate-500 leading-5 italic">
                    Panel: {item.panel_interpretation}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Benchmarking */}
      {report.dimensions?.length > 0 && (
        <div className="card p-6">
          <div className="mb-5">
            <h2 className="text-base font-semibold text-slate-900">IIM Preparedness Benchmark</h2>
            <p className="mt-1 text-xs text-slate-500">
              Your scores vs. what each IIM profile typically achieves across 5 key dimensions. Gap shows where you stand relative to the profile midpoint.
            </p>
          </div>
          <BenchmarkTable
            userDimensions={report.dimensions.map((d) => ({ name: d.name, score: d.score }))}
            disclaimer={report.benchmark_disclaimer}
          />
        </div>
      )}

      {/* Follow-up Coaching */}
      {report.coaching_items?.length > 0 && (
        <div>
          <h2 className="mb-3 text-base font-semibold text-slate-900">Follow-up Coaching</h2>
          <p className="mb-4 text-sm text-slate-500">
            Click each card to reveal the ideal answer and coaching advice.
          </p>
          <div className="space-y-3">
            {report.coaching_items.map((item, idx) => (
              <CoachingCard key={item.question} item={item} index={idx} />
            ))}
          </div>
        </div>
      )}

      {/* Panel Comments */}
      {report.panel_comments?.length > 0 && (
        <div className="card p-5">
          <h2 className="mb-3 text-base font-semibold text-slate-900">Panel Comments</h2>
          <ul className="space-y-2">
            {report.panel_comments.map((comment) => (
              <li key={comment} className="flex items-start gap-2 text-sm text-slate-600">
                <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-navy-400" />
                {comment}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Recommended Improvements */}
      {report.recommended_improvements?.length > 0 && (
        <div className="card p-5">
          <h2 className="mb-3 text-base font-semibold text-slate-900">Recommended Improvements</h2>
          <ul className="space-y-2">
            {report.recommended_improvements.map((rec, idx) => (
              <li key={idx} className="flex items-start gap-3 text-sm text-slate-600">
                <span className="flex-shrink-0 flex h-5 w-5 items-center justify-center rounded-full bg-navy-100 text-navy-700 text-xs font-bold">
                  {idx + 1}
                </span>
                {rec}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/* ─── Small reusable blocks ─────────────────────────────────── */
function MetricCard({ label, value, sub, accent }: { label: string; value: string; sub: string; accent: "green" | "navy" | "amber" | "neutral" }) {
  const colours = {
    green:   "text-emerald-700",
    navy:    "text-navy-700",
    amber:   "text-amber-700",
    neutral: "text-slate-800",
  };
  return (
    <div className="card p-5 animate-slide-up">
      <p className="text-label">{label}</p>
      <p className={`mt-2 text-2xl font-bold tabular-nums ${colours[accent]}`}>{value}</p>
      <p className="mt-1 text-xs text-slate-400">{sub}</p>
    </div>
  );
}

function ListCard({ title, items, colour }: { title: string; items: string[]; colour: "emerald" | "rose" | "amber" }) {
  const cls = {
    emerald: { header: "text-emerald-800", bg: "bg-emerald-50", border: "border-emerald-200", bullet: "bg-emerald-500" },
    rose:    { header: "text-rose-800",    bg: "bg-rose-50",    border: "border-rose-200",    bullet: "bg-rose-500" },
    amber:   { header: "text-amber-800",   bg: "bg-amber-50",   border: "border-amber-200",   bullet: "bg-amber-500" },
  }[colour];

  return (
    <div className={`card p-5 ${cls.bg} border ${cls.border}`}>
      <h3 className={`mb-3 text-sm font-semibold ${cls.header}`}>{title}</h3>
      {items.length ? (
        <ul className="space-y-2">
          {items.map((item) => (
            <li key={item} className="flex items-start gap-2 text-sm text-slate-700">
              <span className={`mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full ${cls.bullet}`} />
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-slate-400 italic">None recorded.</p>
      )}
    </div>
  );
}
