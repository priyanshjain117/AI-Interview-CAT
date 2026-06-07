import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PANELIQ — AI MBA Interview Coaching Platform",
  description:
    "Practice IIM-style MBA panel interviews with AI interviewers. Track your progress, receive evidence-based reports, and download coaching feedback.",
  keywords: "MBA interview, IIM interview preparation, CAT interview coaching, AI interview practice",
  openGraph: {
    title: "PANELIQ — AI MBA Interview Coaching",
    description: "Practice IIM-style panel interviews, track improvement, and download coaching reports.",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
