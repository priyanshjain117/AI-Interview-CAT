"use client";

export function SubtitlePanel({
  text,
  status
}: {
  text: string;
  status: "idle" | "listening" | "processing" | "speaking";
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
      <div className="mb-3 flex items-center justify-between gap-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Live Subtitles
        </h2>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold capitalize text-slate-700">
          {status}
        </span>
      </div>
      <p className="min-h-20 text-xl font-medium leading-9 text-slate-950">
        {text || "Start the interview to hear the panel's first question."}
      </p>
    </section>
  );
}
