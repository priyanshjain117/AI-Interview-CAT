"use client";

// Fixed IIM reference score ranges — independent of user score.
// These are the same values used by intelligence.py _benchmarking().
const IIM_REFS: Record<string, Record<string, [number, number]>> = {
  "Average CAT Aspirant": {
    "Communication clarity": [5.0, 6.2],
    "Leadership potential":  [4.8, 6.0],
    "Business awareness":    [4.5, 5.8],
    "Academic depth":        [5.2, 6.5],
    "Career clarity":        [4.8, 6.0],
  },
  "Typical IIM Convert Candidate": {
    "Communication clarity": [6.5, 7.5],
    "Leadership potential":  [6.2, 7.2],
    "Business awareness":    [6.0, 7.2],
    "Academic depth":        [6.5, 7.8],
    "Career clarity":        [6.5, 7.5],
  },
  "Strong IIM ABC Candidate": {
    "Communication clarity": [7.8, 9.0],
    "Leadership potential":  [7.5, 9.0],
    "Business awareness":    [7.5, 8.8],
    "Academic depth":        [7.8, 9.0],
    "Career clarity":        [7.8, 9.2],
  },
};

const PROFILE_ORDER = [
  "Average CAT Aspirant",
  "Typical IIM Convert Candidate",
  "Strong IIM ABC Candidate",
];

const PROFILE_STYLE: Record<string, { badge: string; header: string; label: string }> = {
  "Average CAT Aspirant":         { badge: "bg-stone-100 text-stone-700 border-stone-200",      header: "text-stone-600",   label: "CAT Aspirant" },
  "Typical IIM Convert Candidate":{ badge: "bg-navy-50 text-navy-700 border-navy-200",          header: "text-navy-700",    label: "IIM Convert" },
  "Strong IIM ABC Candidate":     { badge: "bg-emerald-50 text-emerald-800 border-emerald-200", header: "text-emerald-700", label: "Strong IIM ABC" },
};

const DIM_LABELS: Record<string, string> = {
  "Communication clarity": "Communication",
  "Leadership potential":  "Leadership",
  "Business awareness":    "Business Awareness",
  "Academic depth":        "Academic Depth",
  "Career clarity":        "Career Clarity / MBA Fit",
};

type UserDimension = { name: string; score: number | null };

function GapBar({ score, lo, hi }: { score: number; lo: number; hi: number }) {
  const mid = (lo + hi) / 2;
  const gap = score - mid;
  const isAbove = gap > 0.3;
  const isBelow = gap < -0.3;

  return (
    <div className="flex items-center gap-2 text-xs">
      <div className="relative h-1.5 w-20 rounded-full bg-slate-100">
        {/* reference range band */}
        <div
          className="absolute h-full rounded-full bg-slate-300"
          style={{
            left:  `${((lo - 1) / 9) * 100}%`,
            width: `${((hi - lo) / 9) * 100}%`,
          }}
        />
        {/* user score dot */}
        {score !== null && (
          <div
            className={`absolute -top-0.5 h-2.5 w-2.5 -translate-x-1/2 rounded-full border-2 border-white ${
              isAbove ? "bg-emerald-500" : isBelow ? "bg-rose-500" : "bg-navy-600"
            }`}
            style={{ left: `${((score - 1) / 9) * 100}%` }}
          />
        )}
      </div>
      <span
        className={`font-semibold tabular-nums ${
          isAbove ? "text-emerald-700" : isBelow ? "text-rose-600" : "text-navy-700"
        }`}
      >
        {gap > 0 ? "+" : ""}{gap.toFixed(1)}
      </span>
      <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
        isAbove ? "bg-emerald-50 text-emerald-700" : isBelow ? "bg-rose-50 text-rose-700" : "bg-slate-100 text-slate-600"
      }`}>
        {isAbove ? "Above" : isBelow ? "Below" : "Within"}
      </span>
    </div>
  );
}

export function BenchmarkTable({
  userDimensions,
  disclaimer,
}: {
  userDimensions?: UserDimension[];
  disclaimer?: string;
}) {
  const scoreMap: Record<string, number | null> = {};
  (userDimensions ?? []).forEach((d) => {
    scoreMap[d.name] = d.score;
  });

  const dimensions = Object.keys(DIM_LABELS);

  return (
    <div className="space-y-4">
      {/* Header legend */}
      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" />
          Above profile range
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full bg-navy-600" />
          Within profile range
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full bg-rose-500" />
          Below profile range
        </span>
        <span className="ml-auto italic text-slate-400">Reference range: min–max on a 1–10 scale</span>
      </div>

      {/* Per-profile cards */}
      {PROFILE_ORDER.map((profileName) => {
        const refs = IIM_REFS[profileName];
        const style = PROFILE_STYLE[profileName];
        if (!refs) return null;
        return (
          <div key={profileName} className="rounded-xl border border-slate-200 bg-white overflow-hidden">
            <div className={`border-b border-slate-100 px-5 py-3 ${style.header}`}>
              <span className={`inline-block rounded-full border px-3 py-0.5 text-xs font-bold ${style.badge}`}>
                {style.label}
              </span>
            </div>
            <div className="divide-y divide-slate-100">
              {dimensions.map((dimName) => {
                const [lo, hi] = refs[dimName] ?? [5, 7];
                const userScore = scoreMap[dimName] ?? null;
                const hasScore = userScore !== null;
                return (
                  <div key={dimName} className="grid grid-cols-[1fr_auto_1fr] items-center gap-4 px-5 py-3">
                    {/* Dimension name */}
                    <p className="text-sm font-medium text-slate-700">{DIM_LABELS[dimName]}</p>

                    {/* Reference range (center) */}
                    <div className="text-center">
                      <p className="text-[11px] text-slate-400 mb-0.5">IIM Reference</p>
                      <p className="text-sm font-bold text-slate-700 tabular-nums">{lo.toFixed(1)}–{hi.toFixed(1)}</p>
                    </div>

                    {/* User score + gap bar (right) */}
                    <div className="flex flex-col items-end gap-1">
                      <div className="flex items-baseline gap-1.5">
                        <p className="text-[11px] text-slate-400">Your score</p>
                        <p className={`text-sm font-bold tabular-nums ${
                          !hasScore ? "text-slate-400" :
                          userScore! >= hi ? "text-emerald-700" :
                          userScore! >= lo ? "text-navy-700" :
                          "text-rose-600"
                        }`}>
                          {hasScore ? userScore!.toFixed(1) : "—"}
                        </p>
                      </div>
                      {hasScore && (
                        <GapBar score={userScore!} lo={lo} hi={hi} />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}

      {disclaimer && (
        <p className="text-xs leading-5 text-slate-400 italic">{disclaimer}</p>
      )}
    </div>
  );
}
