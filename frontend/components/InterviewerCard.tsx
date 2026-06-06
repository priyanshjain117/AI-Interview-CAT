"use client";

import { clsx } from "clsx";
import { AudioLines } from "lucide-react";
import type { Interviewer, InterviewerId } from "@/lib/types";

const initials: Record<InterviewerId, string> = {
  academic: "MR",
  pressure: "AM",
  mba: "AS"
};

export function InterviewerCard({
  interviewer,
  isActive,
  isSpeaking
}: {
  interviewer: Interviewer;
  isActive: boolean;
  isSpeaking: boolean;
}) {
  return (
    <section
      className={clsx(
        "relative flex min-h-[220px] flex-col justify-between rounded-lg border bg-white p-5 shadow-panel transition",
        isActive ? "border-navy-700 speaking-panel" : "border-slate-200"
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="grid h-12 w-12 place-items-center rounded-full bg-navy-900 text-sm font-semibold text-white">
            {initials[interviewer.id]}
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-950">{interviewer.name}</h2>
            <p className="text-sm font-medium text-navy-700">{interviewer.role}</p>
          </div>
        </div>
        {isActive ? (
          <span className="rounded-full bg-navy-900 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-white">
            Speaking
          </span>
        ) : (
          <span className="rounded-full border border-slate-200 px-3 py-1 text-xs font-medium text-slate-500">
            Silent
          </span>
        )}
      </div>

      <p className="max-w-xl text-sm leading-6 text-slate-600">{interviewer.focus}</p>

      <div className="flex h-9 items-end gap-1.5 text-navy-700">
        {isSpeaking ? (
          <>
            <span className="wave-bar h-7 w-1.5 rounded-full bg-navy-700" />
            <span className="wave-bar h-7 w-1.5 rounded-full bg-navy-700" />
            <span className="wave-bar h-7 w-1.5 rounded-full bg-navy-700" />
            <span className="wave-bar h-7 w-1.5 rounded-full bg-navy-700" />
          </>
        ) : (
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <AudioLines className="h-4 w-4" />
            Awaiting turn
          </div>
        )}
      </div>
    </section>
  );
}
