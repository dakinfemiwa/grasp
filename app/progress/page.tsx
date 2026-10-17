import Link from "next/link";

// Placeholder route; the full screen is built in Stage 7.
export default function ProgressPage() {
  return (
    <main className="min-h-screen bg-[#080d18] px-6 py-10 text-slate-100">
      <Link href="/" className="text-sm text-cyan-300 hover:underline">
        ← Dashboard
      </Link>
      <h1 className="mt-6 text-2xl font-semibold tracking-tight">Progress</h1>
      <p className="mt-2 text-sm text-slate-400">Coming in Stage 7.</p>
    </main>
  );
}
