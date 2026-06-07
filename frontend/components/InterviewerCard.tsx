"use client";

import type { Interviewer, InterviewerId } from "@/lib/types";

const INITIALS: Record<InterviewerId, string> = {
  academic: "MR",
  pressure: "AM",
  mba: "AS",
};

const AVATAR_COLOR: Record<InterviewerId, string> = {
  academic: "from-navy-900 to-[#162c58]",
  pressure: "from-slate-800 to-slate-700",
  mba:      "from-[#1e4d3a] to-[#2d6a50]",
};

/** 5-bar animated equalizer shown when this panelist is speaking */
function EqualizerBars() {
  return (
    <div className="flex items-end gap-[3px] h-8" aria-label="Speaking">
      {[20, 28, 36, 24, 32].map((h, i) => (
        <span
          key={i}
          className="eq-bar w-[4px] rounded-full bg-navy-700"
          style={{ height: `${h}px` }}
        />
      ))}
    </div>
  );
}

/** Three bouncing dots shown for an awaiting panelist */
function ThinkingDots() {
  return (
    <div className="flex items-center gap-1.5" aria-label="Awaiting turn">
      <span className="thinking-dot h-1.5 w-1.5 bg-slate-300" />
      <span className="thinking-dot h-1.5 w-1.5 bg-slate-300" />
      <span className="thinking-dot h-1.5 w-1.5 bg-slate-300" />
      <span className="ml-1 text-xs text-slate-400">Awaiting turn</span>
    </div>
  );
}

export function InterviewerCard({
  interviewer,
  isActive,
  isSpeaking,
}: {
  interviewer: Interviewer;
  isActive: boolean;
  isSpeaking: boolean;
}) {
  return (
    <section
      className={[
        "relative flex min-h-[220px] flex-col justify-between rounded-xl border bg-white p-5",
        "transition-all duration-500",
        isActive
          ? "border-navy-700 panel-active"
          : "border-slate-200 shadow-sm hover:shadow-md",
      ].join(" ")}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          {/* Avatar */}
          <div
            className={[
              "grid h-12 w-12 flex-shrink-0 place-items-center rounded-full bg-gradient-to-br",
              "text-sm font-bold text-white select-none",
              AVATAR_COLOR[interviewer.id],
              isSpeaking ? "avatar-speaking" : "avatar-idle",
            ].join(" ")}
          >
            {INITIALS[interviewer.id]}
          </div>

          <div>
            <h2 className="text-base font-semibold text-slate-950">{interviewer.name}</h2>
            <p className="text-sm font-medium text-navy-700">{interviewer.role}</p>
          </div>
        </div>

        {/* Status badge */}
        {isActive ? (
          <span className="speaking-badge rounded-full bg-navy-900 px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-white">
            Speaking
          </span>
        ) : (
          <span className="rounded-full border border-slate-200 px-3 py-1 text-[11px] font-medium text-slate-400">
            Silent
          </span>
        )}
      </div>

      {/* Focus description */}
      <p className="mt-3 max-w-xl text-sm leading-6 text-slate-500">{interviewer.focus}</p>

      {/* Bottom animation row */}
      <div className="mt-4 flex h-9 items-end">
        {isSpeaking ? <EqualizerBars /> : <ThinkingDots />}
      </div>
    </section>
  );
}
