import Link from "next/link";

import { AuthControls } from "@/components/auth-controls";
import { EvidenceTable } from "@/components/evidence";

export default function ProgressPage() {
  return (
    <main className="min-h-screen bg-[#080d18] text-slate-100">
      <div className="mx-auto max-w-4xl px-5 py-8 sm:px-8">
        <header className="flex items-center justify-between gap-4">
          <Link href="/" className="text-sm text-cyan-300 hover:underline">
            ← Dashboard
          </Link>
          <AuthControls />
        </header>
        <h1 className="mt-6 text-2xl font-semibold tracking-tight">Progress</h1>
        <p className="mt-2 text-sm leading-6 text-slate-400">
          Every marked step of every attempt is recorded against the objective
          it assesses.
        </p>
        <div className="mt-8">
          <EvidenceTable />
        </div>
      </div>
    </main>
  );
}
