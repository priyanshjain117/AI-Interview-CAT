"use client";

type Verdict = string;

const VERDICT_CONFIG: Record<string, { cls: string; label: string }> = {
  "Strong Admit":       { cls: "verdict-strong", label: "Strong Admit" },
  "Likely Convert":     { cls: "verdict-strong", label: "Likely Convert" },
  "Strong Hire":        { cls: "verdict-strong", label: "Strong Hire" },
  "Borderline Admit":   { cls: "verdict-good",   label: "Borderline Admit" },
  "Borderline":         { cls: "verdict-good",   label: "Borderline" },
  "Lean Hire":          { cls: "verdict-mid",    label: "Lean Hire" },
  "Waitlist":           { cls: "verdict-mid",    label: "Waitlist" },
  "Lean Reject":        { cls: "verdict-weak",   label: "Lean Reject" },
  "Needs Improvement":  { cls: "verdict-weak",   label: "Needs Improvement" },
  "Strong Reject":      { cls: "verdict-weak",   label: "Strong Reject" },
};

export function ScoreBadge({ verdict, size = "md" }: { verdict: Verdict; size?: "sm" | "md" | "lg" }) {
  const config = VERDICT_CONFIG[verdict] ?? { cls: "verdict-mid", label: verdict };
  const sizeClass = size === "sm"
    ? "px-2 py-0.5 text-xs"
    : size === "lg"
    ? "px-3.5 py-1.5 text-sm"
    : "px-2.5 py-1 text-xs";

  return (
    <span
      className={`${config.cls} ${sizeClass} inline-block rounded-full font-semibold tracking-wide`}
    >
      {config.label}
    </span>
  );
}

export function ScoreRing({ score, size = 80 }: { score: number; size?: number }) {
  const r = (size - 8) / 2;
  const circ = 2 * Math.PI * r;
  const fill = Math.min(score / 10, 1);
  const dash = circ * fill;
  const gap = circ - dash;

  const colour =
    score >= 8 ? "#059669" :
    score >= 7 ? "#1e3d75" :
    score >= 5.5 ? "#d97706" :
    "#be123c";

  return (
    <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e2e8f0" strokeWidth={7} />
      <circle
        cx={size / 2} cy={size / 2} r={r} fill="none"
        stroke={colour} strokeWidth={7}
        strokeDasharray={`${dash} ${gap}`}
        strokeLinecap="round"
        style={{ transition: "stroke-dasharray 0.6s ease" }}
      />
      <text
        x="50%" y="52%" dominantBaseline="middle" textAnchor="middle"
        fill={colour} fontSize={size / 3.8} fontWeight="700"
        style={{ transform: `rotate(90deg)`, transformOrigin: "center" }}
      >
        {score.toFixed(1)}
      </text>
    </svg>
  );
}
