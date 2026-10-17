import {
    ArrowUpRight,
    BarChart3,
    BookOpen,
    CheckCircle2,
    ChevronRight,
    CircleHelp,
    Flame,
    Gauge,
    Home as HomeIcon,
    Menu,
    Settings2,
    Sparkles,
    Target,
} from "lucide-react";

import { AuthControls } from "@/components/auth-controls";
import { PracticePanel } from "@/components/practice-panel";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { UserGreeting } from "@/components/user-greeting";
import { getHealth } from "@/lib/api";
import { cn } from "@/lib/utils";

const objectives = [
  {
    name: "Construct a mathematical model",
    detail: "Form an equation that represents a situation",
    progress: 72,
  },
  {
    name: "Interpret results",
    detail: "Explain a solution in the original context",
    progress: 48,
  },
  {
    name: "Evaluate a model",
    detail: "Identify limitations and refinements",
    progress: 31,
  },
];

const activity = [
  {
    title: "Quadratic modelling",
    result: "4 / 5 correct",
    time: "Today",
    tone: "success" as const,
  },
  {
    title: "Linear modelling",
    result: "3 / 5 correct",
    time: "Yesterday",
    tone: "warning" as const,
  },
  {
    title: "Trigonometric modelling",
    result: "2 / 4 correct",
    time: "Mon",
    tone: "muted" as const,
  },
];

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
                Your next set changes the question style, not the skill.
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
                  Your adaptive session
                </Badge>
                <h2 className="mt-5 max-w-lg text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">
                  Turn today&apos;s mistakes into tomorrow&apos;s confidence.
                </h2>
                <p className="mt-4 max-w-md text-sm leading-6 text-slate-300">
                  Continue with a quadratic modelling question. Same skill, a
                  fresh representation.
                </p>
                <a href="/practice" className={cn(buttonVariants(), "mt-7")}>
                  Continue practice <ChevronRight className="size-4" />
                </a>
                <div className="mt-8 flex items-center gap-3 text-xs text-slate-400">
                  <div className="flex -space-x-1">
                    <span className="size-6 rounded-full border-2 border-[#102236] bg-cyan-200" />
                    <span className="size-6 rounded-full border-2 border-[#102236] bg-violet-300" />
                    <span className="size-6 rounded-full border-2 border-[#102236] bg-amber-200" />
                  </div>{" "}
                  5 questions · approximately 8 minutes
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">This week</CardTitle>
                  <Flame className="size-5 text-amber-300" />
                </div>
                <CardDescription>Small steps compound.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-end gap-3">
                  <span className="text-5xl font-semibold tracking-tight">
                    68%
                  </span>
                  <span className="mb-2 text-sm text-emerald-300">
                    +12% <span className="text-slate-500">vs last week</span>
                  </span>
                </div>
                <Progress className="mt-5" value={68} />
                <div className="mt-3 flex justify-between text-xs text-slate-500">
                  <span>17 attempts</span>
                  <span>Target: 75%</span>
                </div>
              </CardContent>
            </Card>
          </div>

          <PracticePanel />

          <div
            id="progress"
            className="mt-8 grid gap-5 xl:grid-cols-[1.2fr_0.8fr]"
          >
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Learning objectives</CardTitle>
                    <CardDescription className="mt-1">
                      Your progress across the modelling skills.
                    </CardDescription>
                  </div>
                  <Target className="size-5 text-cyan-300" />
                </div>
              </CardHeader>
              <CardContent className="space-y-5">
                {objectives.map((objective) => (
                  <div key={objective.name}>
                    <div className="mb-2 flex items-center justify-between gap-4">
                      <div>
                        <p className="text-sm font-medium text-slate-200">
                          {objective.name}
                        </p>
                        <p className="mt-0.5 text-xs text-slate-500">
                          {objective.detail}
                        </p>
                      </div>
                      <span className="text-sm font-semibold text-slate-300">
                        {objective.progress}%
                      </span>
                    </div>
                    <Progress value={objective.progress} />
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Recent practice</CardTitle>
                    <CardDescription className="mt-1">
                      Your latest adaptive sets.
                    </CardDescription>
                  </div>
                  <Gauge className="size-5 text-violet-300" />
                </div>
              </CardHeader>
              <CardContent className="space-y-1">
                {activity.map((item) => (
                  <div
                    key={item.title}
                    className="flex items-center gap-3 rounded-lg px-2 py-3"
                  >
                    <CheckCircle2
                      className={cn(
                        "size-4 shrink-0",
                        item.tone === "success"
                          ? "text-emerald-300"
                          : item.tone === "warning"
                            ? "text-amber-300"
                            : "text-slate-500",
                      )}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-slate-200">
                        {item.title}
                      </p>
                      <p className="text-xs text-slate-500">{item.time}</p>
                    </div>
                    <Badge variant={item.tone}>{item.result}</Badge>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>

          <footer
            id="how-it-works"
            className="mt-8 flex flex-col gap-3 border-t border-slate-800/80 py-6 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between"
          >
            <p>Grasp adapts the next question to your last attempt.</p>
            <p>Built for thoughtful practice, not streaks.</p>
          </footer>
        </section>
      </div>
    </main>
  );
}
