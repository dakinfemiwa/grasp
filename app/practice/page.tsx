import Link from "next/link";

import { AuthControls } from "@/components/auth-controls";
import { PracticeSession } from "@/components/practice/practice-session";

export default function PracticePage() {
  return (
    <main className="min-h-screen bg-[#080d18] text-slate-100">
      <div className="mx-auto max-w-3xl px-5 py-8 sm:px-8">
        <header className="flex items-center justify-between gap-4">
          <Link href="/" className="text-sm text-cyan-300 hover:underline">
            ← Dashboard
          </Link>
          <AuthControls />
        </header>
        <h1 className="mt-6 text-2xl font-semibold tracking-tight">
          Modelling practice
        </h1>
        <p className="mt-2 text-sm leading-6 text-slate-400">
          Build a model from a situation, solve it and interpret the result.
          Each step is marked separately, so you can see which modelling skill
          needs work.
        </p>
        <div className="mt-8">
          <PracticeSession />
        </div>
      </div>
    </main>
  );
}
