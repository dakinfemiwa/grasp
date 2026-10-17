"use client";

import { CheckCircle2, Gauge, Target } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  describeApiError,
  type EvidenceSummary,
  practiceApi,
  type StepOutcome,
} from "@/lib/api";
import { useWithToken } from "@/lib/use-practice-api";
import { cn } from "@/lib/utils";

const STEP_BADGE: Record<StepOutcome, "success" | "warning" | "muted"> = {
  correct: "success",
  incorrect: "warning",
  missing: "muted",
};

function useEvidenceSummary() {
  const withToken = useWithToken();
  const [summary, setSummary] = useState<EvidenceSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    withToken(practiceApi.evidenceSummary)
      .then((s) => !cancelled && setSummary(s))
      .catch((e) => !cancelled && setError(describeApiError(e)));
    return () => {
      cancelled = true;
    };
  }, [withToken]);
  return { summary, error };
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function Status({ error, loading }: { error: string | null; loading: boolean }) {
  if (error) return <p className="text-sm text-amber-200">{error}</p>;
  if (loading) return <p className="text-sm text-slate-500">Loading…</p>;
  return null;
}

/** Full per-objective table for the progress page. */
export function EvidenceTable() {
  const { summary, error } = useEvidenceSummary();
  return (
    <Card>
      <CardHeader>
        <CardTitle>Evidence by objective</CardTitle>
        <CardDescription>
          {summary?.note ??
            "Counts of recorded evidence per objective. This is not an estimate of mastery."}{" "}
          A question assesses several objectives, and each marked step counts
          once for its objective.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Status error={error} loading={!summary} />
        {summary && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="py-2 pr-4 font-medium">Objective</th>
                  <th className="py-2 pr-4 text-right font-medium">Correct</th>
                  <th className="py-2 pr-4 text-right font-medium">
                    Incorrect
                  </th>
                  <th className="py-2 pr-4 text-right font-medium">Missing</th>
                  <th className="py-2 font-medium">Last</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {summary.objectives.map((o) => (
                  <tr key={o.id}>
                    <td className="py-3 pr-4">
                      <span className="text-slate-500">{o.id}</span>{" "}
                      <span className="text-slate-200">{o.title}</span>
                    </td>
                    <td className="py-3 pr-4 text-right tabular-nums">
                      {o.correct}
                    </td>
                    <td className="py-3 pr-4 text-right tabular-nums">
                      {o.incorrect}
                    </td>
                    <td className="py-3 pr-4 text-right tabular-nums">
                      {o.missing}
                    </td>
                    <td className="py-3">
                      {o.last_outcome ? (
                        <Badge variant={STEP_BADGE[o.last_outcome]}>
                          {o.last_outcome}
                        </Badge>
                      ) : (
                        <span className="text-slate-600">No evidence yet</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/** Dashboard: totals card. */
export function EvidenceTotals() {
  const { summary, error } = useEvidenceSummary();
  const assessed = summary?.objectives.filter(
    (o) => o.correct + o.incorrect + o.missing > 0,
  ).length;
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Your evidence</CardTitle>
          <Gauge className="size-5 text-violet-300" />
        </div>
        <CardDescription>What you have attempted so far.</CardDescription>
      </CardHeader>
      <CardContent>
        <Status error={error} loading={!summary} />
        {summary && (
          <>
            <p className="text-5xl font-semibold tracking-tight tabular-nums">
              {summary.total_attempts}
            </p>
            <p className="mt-1 text-sm text-slate-400">
              {summary.total_attempts === 1 ? "attempt" : "attempts"} recorded
            </p>
            <p className="mt-4 text-sm text-slate-400">
              Evidence for{" "}
              <span className="font-semibold text-slate-200">
                {assessed} of {summary.objectives.length}
              </span>{" "}
              modelling objectives.
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}

/** Dashboard: objectives with evidence, and recent attempts. */
export function EvidenceOverview() {
  const { summary, error } = useEvidenceSummary();
  const withEvidence =
    summary?.objectives.filter((o) => o.correct + o.incorrect + o.missing > 0) ??
    [];
  return (
    <div className="mt-8 grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Modelling objectives</CardTitle>
              <CardDescription className="mt-1">
                Correct steps out of all marked steps, per objective. Evidence,
                not a mastery score.
              </CardDescription>
            </div>
            <Target className="size-5 text-cyan-300" />
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <Status error={error} loading={!summary} />
          {summary && withEvidence.length === 0 && (
            <p className="text-sm text-slate-500">
              No evidence yet. Answer a question to see it here.
            </p>
          )}
          {withEvidence.map((o) => {
            const total = o.correct + o.incorrect + o.missing;
            return (
              <div key={o.id}>
                <div className="mb-2 flex items-center justify-between gap-4 text-sm">
                  <p className="text-slate-200">
                    <span className="text-slate-500">{o.id}</span> {o.title}
                  </p>
                  <span className="tabular-nums text-slate-400">
                    {o.correct} / {total}
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
                  <div
                    className="h-full rounded-full bg-cyan-300"
                    style={{ width: `${(100 * o.correct) / total}%` }}
                  />
                </div>
              </div>
            );
          })}
          <Link
            href="/progress"
            className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "px-0 text-cyan-300")}
          >
            See all objectives
          </Link>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent practice</CardTitle>
          <CardDescription className="mt-1">Your latest attempts.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-1">
          {summary && summary.recent.length === 0 && (
            <p className="text-sm text-slate-500">Nothing yet.</p>
          )}
          {summary?.recent.map((r) => (
            <div key={r.evidence_id} className="flex items-center gap-3 rounded-lg px-2 py-3">
              <CheckCircle2
                className={cn(
                  "size-4 shrink-0",
                  r.outcome === "correct" ? "text-emerald-300" : "text-amber-300",
                )}
              />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-slate-200">
                  {r.template_title}
                </p>
                <p className="text-xs text-slate-500">
                  {r.scenario_title} · {formatDate(r.created_at)}
                </p>
              </div>
              <Badge variant={r.outcome === "correct" ? "success" : "warning"}>
                {r.outcome}
              </Badge>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
