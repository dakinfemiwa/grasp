import {
    ArrowUpRight,
    BarChart3,
    BookOpen,
    ChevronRight,
    CircleHelp,
    Home as HomeIcon,
    Menu,
    Settings2,
    Sparkles,
} from "lucide-react";

import { AuthControls } from "@/components/auth-controls";
import { EvidenceOverview, EvidenceTotals } from "@/components/evidence";
import { PracticePanel } from "@/components/practice-panel";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { UserGreeting } from "@/components/user-greeting";
import { getHealth } from "@/lib/api";
import { cn } from "@/lib/utils";

export default async function Home() {
  let health: Awaited<ReturnType<typeof getHealth>> | null = null;

  try {
    health = await getHealth();
  } catch {
    health = null;
  }

  return (
    <main className="min-h-screen bg-[#080d18] text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-[1500px]">
        <aside className="hidden w-64 shrink-0 border-r border-slate-800/80 px-5 py-7 lg:block">
          <div className="flex items-center gap-3 px-2">
            <div className="grid size-9 place-items-center rounded-xl bg-cyan-300 text-slate-950 shadow-[0_0_24px_rgba(103,232,249,0.2)]">
              <Sparkles className="size-5" />
            </div>
            <div>
              <p className="font-semibold tracking-tight">grasp</p>
              <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">
                adaptive maths
              </p>
            </div>
          </div>

          <nav className="mt-12 space-y-1" aria-label="Main navigation">
            <a
              className="flex items-center gap-3 rounded-lg bg-slate-800/80 px-3 py-2.5 text-sm font-medium text-cyan-200"
              href="#overview"
            >
              <HomeIcon className="size-4" />
              Overview
            </a>
            <a
              className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-slate-400 transition hover:bg-slate-900 hover:text-slate-100"
              href="/practice"
            >
              <BookOpen className="size-4" />
              Practice
            </a>
            <a
              className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-slate-400 transition hover:bg-slate-900 hover:text-slate-100"
              href="/progress"
            >
              <BarChart3 className="size-4" />
              Progress
            </a>
          </nav>

          <div className="mt-auto pt-32">
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
                <CircleHelp className="size-4 text-cyan-300" />
                Need a nudge?
              </div>
              <p className="mt-2 text-xs leading-5 text-slate-500">
                A variation keeps the skill and changes the numbers or context.
              </p>
              <a
                href="#how-it-works"
                className={cn(
                  buttonVariants({ variant: "ghost", size: "sm" }),
                  "mt-3 px-0 text-cyan-300",
                )}
              >
                How it works <ArrowUpRight className="size-3.5" />
              </a>
            </div>
            <a
              className="mt-5 flex items-center gap-3 px-3 py-2 text-sm text-slate-500 hover:text-slate-200"
              href="#settings"
            >
              <Settings2 className="size-4" />
              Settings
            </a>
          </div>
        </aside>

        <section className="min-w-0 flex-1 px-5 py-6 sm:px-8 lg:px-12 lg:py-8">
          <header className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 lg:hidden">
              <Menu className="size-5 text-slate-400" />
              <span className="font-semibold">grasp</span>
            </div>
            <UserGreeting />
            <div className="flex items-center gap-3">
              <div className="hidden items-center gap-2 rounded-full border border-slate-800 px-3 py-1.5 text-xs text-slate-400 sm:flex">
                <span
                  className={cn(
                    "size-2 rounded-full",
                    health ? "bg-emerald-400" : "bg-rose-400",
                  )}
                />
                {health ? "All systems ready" : "Offline mode"}
              </div>
              <AuthControls />
            </div>
          </header>

          <div
            id="overview"
            className="mt-8 grid gap-5 xl:grid-cols-[1.35fr_0.65fr]"
          >
            <Card className="relative overflow-hidden border-cyan-300/20 bg-[radial-gradient(circle_at_90%_0%,rgba(103,232,249,0.16),transparent_38%),linear-gradient(135deg,#102236,#0d1524)]">
              <CardContent className="relative p-6 sm:p-8">
                <Badge>
                  <Sparkles className="mr-1.5 size-3.5" />
                  Mathematical modelling
                </Badge>
                <h2 className="mt-5 max-w-lg text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">
                  Turn today&apos;s mistakes into tomorrow&apos;s confidence.
                </h2>
                <p className="mt-4 max-w-md text-sm leading-6 text-slate-300">
                  Build a model from a real situation, solve it and interpret
                  the answer. Every step is marked against the modelling skill
                  it shows.
                </p>
                <a href="/practice" className={cn(buttonVariants(), "mt-7")}>
                  Start practice <ChevronRight className="size-4" />
                </a>
              </CardContent>
            </Card>

            <EvidenceTotals />
          </div>

          <PracticePanel />

          <div id="progress">
            <EvidenceOverview />
          </div>

          <footer
            id="how-it-works"
            className="mt-8 flex flex-col gap-3 border-t border-slate-800/80 py-6 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between"
          >
            <p>Grasp records evidence for each modelling skill you show.</p>
            <p>Built for thoughtful practice, not streaks.</p>
          </footer>
        </section>
      </div>
    </main>
  );
}
