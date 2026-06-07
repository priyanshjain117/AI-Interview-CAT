"use client";

import { useEffect, useRef, useState } from "react";

interface SessionTimerProps {
  running: boolean;
  maxSeconds?: number;
  onTimeUp?: () => void;
}

export function SessionTimer({ running, maxSeconds, onTimeUp }: SessionTimerProps) {
  const [elapsed, setElapsed] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const onTimeUpRef = useRef(onTimeUp);
  const calledRef = useRef(false);

  useEffect(() => { onTimeUpRef.current = onTimeUp; }, [onTimeUp]);

  useEffect(() => {
    if (!running) return;
    intervalRef.current = setInterval(() => {
      setElapsed((prev) => prev + 1);
    }, 1000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [running]);

  // Fire onTimeUp once when countdown reaches 0
  useEffect(() => {
    if (!maxSeconds || calledRef.current) return;
    if (elapsed >= maxSeconds) {
      calledRef.current = true;
      onTimeUpRef.current?.();
    }
  }, [elapsed, maxSeconds]);

  const remaining = maxSeconds ? Math.max(0, maxSeconds - elapsed) : null;
  const display = remaining !== null ? remaining : elapsed;

  const mins = Math.floor(display / 60);
  const secs = display % 60;
  const label = `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;

  // Color urgency
  let colorClass = "text-slate-600";
  let bgClass = "bg-white border-slate-200";
  let dotClass = "bg-emerald-400";

  if (remaining !== null) {
    if (remaining <= 60) {
      colorClass = "text-red-700 font-bold animate-pulse";
      bgClass = "bg-red-50 border-red-300";
      dotClass = "bg-red-500 animate-ping";
    } else if (remaining <= 300) {
      colorClass = "text-amber-700 font-semibold";
      bgClass = "bg-amber-50 border-amber-300";
      dotClass = "bg-amber-400";
    }
  }

  return (
    <div className={`flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-xs transition-all duration-500 ${bgClass}`}>
      <span className={`h-2 w-2 flex-shrink-0 rounded-full ${dotClass}`} />
      <span className={`tabular-nums tracking-wider ${colorClass}`}>
        {remaining !== null ? (remaining <= 60 ? "⏱ " : "") : ""}
        {label}
      </span>
    </div>
  );
}
