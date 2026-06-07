"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, RefreshCw, Loader2 } from "lucide-react";
import { practiceAgain } from "@/lib/api";

type CoachingItem = {
  weakness: string;
  question: string;
  why_panel_would_ask: string;
  ideal_answer: string;
  skills_being_evaluated: string[];
  improvement_advice: string;
  practice_id: string | null;
};

export function CoachingCard({ item, index }: { item: CoachingItem; index: number }) {
  const [open, setOpen] = useState(false);
  const [practicing, setPracticing] = useState(false);
  const [practiced, setPracticed] = useState<string | null>(null);

  async function handlePractice() {
    if (!item.practice_id) return;
    setPracticing(true);
    try {
      const res = await practiceAgain(item.practice_id);
      setPracticed(`Practiced ${res.practiced_count} time${res.practiced_count === 1 ? "" : "s"}`);
    } finally {
      setPracticing(false);
    }
  }

  return (
    <div
      className="card overflow-hidden animate-slide-up"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      {/* Header */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-start justify-between gap-4 p-4 text-left hover:bg-slate-50 transition-colors"
      >
        <div className="flex-1 min-w-0">
          <p className="text-label mb-1">Weakness Identified</p>
          <p className="text-sm font-semibold text-slate-900 leading-snug">{item.weakness}</p>
          <p className="mt-1.5 text-sm text-navy-700 font-medium leading-snug">Q: {item.question}</p>
        </div>
        <span className="mt-0.5 flex-shrink-0 text-slate-400">
          {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </span>
      </button>

      {/* Expanded content */}
      {open && (
        <div className="border-t border-slate-100 px-4 pb-4 pt-3 space-y-3 animate-slide-up">
          <div>
            <p className="text-label mb-1">Why the panel asks this</p>
            <p className="text-sm leading-6 text-slate-600">{item.why_panel_would_ask}</p>
          </div>

          <div>
            <p className="text-label mb-1">Ideal answer</p>
            <p className="rounded-lg bg-navy-50 px-3 py-2.5 text-sm leading-6 text-navy-900">
              {item.ideal_answer}
            </p>
          </div>

          {item.improvement_advice && (
            <div>
              <p className="text-label mb-1">Coaching advice</p>
              <p className="text-sm leading-6 text-slate-600">{item.improvement_advice}</p>
            </div>
          )}

          {item.skills_being_evaluated?.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {item.skills_being_evaluated.map((skill) => (
                <span key={skill} className="rounded-full bg-stone-100 px-2.5 py-0.5 text-xs font-medium text-stone-700">
                  {skill}
                </span>
              ))}
            </div>
          )}

          {item.practice_id && (
            <div className="flex items-center gap-3 pt-1">
              <button onClick={handlePractice} disabled={practicing} className="btn btn-secondary gap-2">
                {practicing
                  ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  : <RefreshCw className="h-3.5 w-3.5" />}
                {practicing ? "Recording..." : "Mark Practiced"}
              </button>
              {practiced && (
                <span className="text-xs font-medium text-emerald-700">{practiced}</span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
