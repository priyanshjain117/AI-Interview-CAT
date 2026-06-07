"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

type ProgressPoint = {
  report_id: string | null;
  created_at: string;
  communication: number | null;
  leadership: number | null;
  business_awareness: number | null;
  mba_fit: number | null;
  career_clarity: number | null;
  academic_depth: number | null;
};

const SERIES = [
  { key: "communication",      label: "Communication",      color: "#1e3d75" },
  { key: "leadership",         label: "Leadership",         color: "#059669" },
  { key: "business_awareness", label: "Business Awareness", color: "#d97706" },
  { key: "career_clarity",     label: "Career Clarity",     color: "#7c3aed" },
  { key: "academic_depth",     label: "Academic Depth",     color: "#db2777" },
  { key: "mba_fit",            label: "MBA Fit",            color: "#0891b2" },
] as const;

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-IN", { month: "short", day: "numeric" });
}

export function ScoreChart({ points }: { points: ProgressPoint[] }) {
  if (!points.length) {
    return (
      <div className="flex h-48 items-center justify-center text-sm text-slate-400">
        Complete interviews to build your progress chart.
      </div>
    );
  }

  const data = points.map((p) => ({
    date: formatDate(p.created_at),
    communication: p.communication,
    leadership: p.leadership,
    business_awareness: p.business_awareness,
    mba_fit: p.mba_fit,
    career_clarity: p.career_clarity,
    academic_depth: p.academic_depth,
  }));

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data} margin={{ top: 5, right: 16, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: "#94a3b8" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          domain={[0, 10]}
          ticks={[0, 2, 4, 6, 8, 10]}
          tick={{ fontSize: 11, fill: "#94a3b8" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          contentStyle={{
            background: "#fff",
            border: "1px solid #e2e8f0",
            borderRadius: "8px",
            fontSize: "12px",
            boxShadow: "0 4px 16px rgba(15,23,42,0.10)",
          }}
          // recharts formatter types are overly strict — cast to avoid TS error
          formatter={((value: unknown, name: unknown) => [
            typeof value === "number" ? value.toFixed(1) : "—",
            SERIES.find((s) => s.key === name)?.label ?? String(name),
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          ]) as any}
        />
        <Legend
          iconType="circle"
          iconSize={8}
          wrapperStyle={{ fontSize: "12px", paddingTop: "12px" }}
          formatter={(value) => SERIES.find((s) => s.key === value)?.label ?? value}
        />
        {SERIES.map((s) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            stroke={s.color}
            strokeWidth={2}
            dot={{ r: 4, fill: s.color, strokeWidth: 0 }}
            activeDot={{ r: 6 }}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

export function MiniScoreChart({ points }: { points: ProgressPoint[] }) {
  if (points.length < 2) return null;

  const data = points.map((p) => {
    const scores = [p.communication, p.leadership, p.business_awareness, p.mba_fit, p.career_clarity, p.academic_depth].filter(Boolean) as number[];
    const avg = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null;
    return { date: formatDate(p.created_at), avg };
  });

  return (
    <ResponsiveContainer width="100%" height={80}>
      <LineChart data={data} margin={{ top: 4, right: 4, left: -32, bottom: 0 }}>
        <YAxis domain={[0, 10]} hide />
        <Line
          type="monotone"
          dataKey="avg"
          stroke="#1e3d75"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4 }}
        />
        <Tooltip
          contentStyle={{ fontSize: "11px", borderRadius: "6px", border: "1px solid #e2e8f0" }}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          formatter={((v: unknown) => [typeof v === "number" ? v.toFixed(1) : "—", "Avg Score"]) as any}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
