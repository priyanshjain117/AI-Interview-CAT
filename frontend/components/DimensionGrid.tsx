"use client";

type Dimension = {
  name: string;
  score: number | null;
  evidence: string;
  strengths: string[];
  weaknesses: string[];
  advice: string;
};

function ScoreBar({ score }: { score: number }) {
  const pct = Math.min((score / 10) * 100, 100);
  const colour =
    score >= 8 ? "bg-emerald-600" :
    score >= 7 ? "bg-navy-700" :
    score >= 5.5 ? "bg-amber-500" :
    "bg-rose-600";

  return (
    <div className="mt-2 flex items-center gap-3">
      <div className="progress-bar-track flex-1">
        <div className={`progress-bar-fill ${colour}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 text-right text-sm font-semibold text-slate-800">{score.toFixed(1)}</span>
    </div>
  );
}

export function DimensionGrid({ dimensions }: { dimensions: Dimension[] }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-2">
      {dimensions.map((dim) => (
        <div key={dim.name} className="card p-4 animate-slide-up">
          <div className="flex items-start justify-between gap-2">
            <h4 className="text-sm font-semibold text-slate-900">{dim.name}</h4>
            {dim.score === null ? (
              <span className="text-xs text-slate-400 font-medium">Not tested</span>
            ) : (
              <span
                className={`text-sm font-bold tabular-nums ${
                  dim.score >= 8 ? "text-emerald-700" :
                  dim.score >= 7 ? "text-navy-700" :
                  dim.score >= 5.5 ? "text-amber-700" :
                  "text-rose-700"
                }`}
              >
                {dim.score.toFixed(1)}<span className="text-xs font-normal text-slate-400">/10</span>
              </span>
            )}
          </div>
          {dim.score !== null && <ScoreBar score={dim.score} />}
          <p className="mt-2.5 text-xs leading-5 text-slate-500">{dim.evidence}</p>
          {dim.advice && (
            <p className="mt-2 rounded-md bg-navy-50 px-3 py-2 text-xs leading-5 text-navy-800">
              ★ {dim.advice}
            </p>
          )}
          {dim.strengths.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {dim.strengths.map((s) => (
                <span key={s} className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
                  ✓ {s}
                </span>
              ))}
            </div>
          )}
          {dim.weaknesses.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {dim.weaknesses.map((w) => (
                <span key={w} className="rounded-full bg-rose-50 px-2 py-0.5 text-xs font-medium text-rose-700">
                  ✗ {w}
                </span>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
