"use client";

import { useEffect, useRef, useState } from "react";
import { Camera } from "lucide-react";

export function CandidateCamera() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let stream: MediaStream | null = null;

    async function enableCamera() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { aspectRatio: 16 / 9 },
          audio: false
        });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      } catch {
        setError("Camera permission is needed for the interview room.");
      }
    }

    enableCamera();

    return () => {
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  return (
    <section className="relative min-h-[220px] overflow-hidden rounded-lg border border-slate-200 bg-slate-950 shadow-panel">
      <video
        ref={videoRef}
        className="h-full min-h-[220px] w-full object-cover"
        autoPlay
        playsInline
        muted
      />
      <div className="absolute left-4 top-4 rounded-full bg-white px-3 py-1 text-xs font-semibold uppercase tracking-wide text-slate-700">
        Candidate Webcam
      </div>
      {error ? (
        <div className="absolute inset-0 grid place-items-center bg-slate-900 p-6 text-center text-sm text-white">
          <div>
            <Camera className="mx-auto mb-3 h-8 w-8" />
            {error}
          </div>
        </div>
      ) : null}
    </section>
  );
}
