"use client";

import { useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { apiUrl } from "@/lib/api";
import { supabase } from "@/lib/supabase";

export function ReportDownloadButton({ sessionId }: { sessionId: string }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function downloadPdf() {
    setLoading(true);
    setError("");
    try {
      // Get the current Bearer token from Supabase — this is what the <a href> approach misses.
      const session = supabase ? (await supabase.auth.getSession()).data.session : null;
      const headers: HeadersInit = {};
      if (session?.access_token) {
        headers["Authorization"] = `Bearer ${session.access_token}`;
      }

      const response = await fetch(apiUrl(`/sessions/${sessionId}/report.pdf`), { headers });
      if (!response.ok) {
        throw new Error(`Download failed (${response.status})`);
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `paneliq-report-${sessionId.slice(0, 8)}.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <button onClick={downloadPdf} disabled={loading} className="btn btn-secondary">
        {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
        {loading ? "Downloading..." : "Download PDF"}
      </button>
      {error && <p className="mt-1 text-xs text-rose-600">{error}</p>}
    </div>
  );
}
