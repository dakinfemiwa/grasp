"use client";

import {
  CheckCircle2,
  CircleDashed,
  Lightbulb,
  Loader2,
  RefreshCw,
  Shuffle,
  XCircle,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  type AttemptResult,
  describeApiError,
  type Objective,
  practiceApi,
  type QuestionInstance,
  type ResponseField,
  type StepOutcome,
  type StructuredResponse,
  type TemplateSummary,
} from "@/lib/api";
import { useWithToken } from "@/lib/use-practice-api";
import { cn } from "@/lib/utils";

const OUTCOME_BADGE = {
  correct: "success",
  partial: "warning",
  incorrect: "warning",
  missing: "muted",
} as const;

const inputClass =
  "h-10 w-full rounded-lg border border-slate-700 bg-slate-950/60 px-3 text-sm text-slate-100 placeholder:text-slate-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300";

function OutcomeIcon({ outcome }: { outcome: StepOutcome }) {
  if (outcome === "correct")
    return <CheckCircle2 className="size-4 shrink-0 text-emerald-300" />;
  if (outcome === "incorrect")
    return <XCircle className="size-4 shrink-0 text-amber-300" />;
  return <CircleDashed className="size-4 shrink-0 text-slate-500" />;
}

/** Turns the raw input strings into the typed structured response. */
function buildResponse(
  fields: ResponseField[],
  values: Record<string, string>,
): { response: StructuredResponse; problems: string[] } {
  const response: StructuredResponse = {};
  const problems: string[] = [];
  for (const field of fields) {
    const raw = (values[field.name] ?? "").trim();
    if (!raw) continue;
    if (field.kind === "number") {
      const n = Number(raw);
      if (Number.isFinite(n)) response[field.name] = n;
      else problems.push(`${field.label}: enter a number.`);
    } else if (field.kind === "number_list") {
      const parts = raw.split(/[\s,;]+/).filter(Boolean).map(Number);
      if (parts.every(Number.isFinite)) response[field.name] = parts;
      else problems.push(`${field.label}: separate numbers with commas.`);
    } else {
      response[field.name] = raw;
    }
  }
  return { response, problems };
}

function FieldInput({
  field,
  value,
  disabled,
  onChange,
}: {
  field: ResponseField;
  value: string;
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  const id = `field-${field.name}`;
  return (
    <div>
      <label
        htmlFor={id}
        className="mb-1.5 flex items-baseline justify-between gap-3 text-sm font-medium text-slate-200"
      >
        <span>{field.label}</span>
        {field.unit && (
          <span className="text-xs font-normal text-slate-500">
            {field.unit}
          </span>
        )}
      </label>
      {field.kind === "choice" ? (
        <div id={id} role="radiogroup" className="flex flex-wrap gap-2">
          {field.options.map((option) => (
            <button
              key={option}
              type="button"
              role="radio"
              aria-checked={value === option}
              disabled={disabled}
              onClick={() => onChange(value === option ? "" : option)}
              className={cn(
                "rounded-lg border px-3 py-2 text-left text-sm transition-colors disabled:opacity-60",
                value === option
                  ? "border-cyan-300 bg-cyan-300/10 text-cyan-100"
                  : "border-slate-700 text-slate-300 hover:border-slate-500",
              )}
            >
              {option}
            </button>
          ))}
        </div>
      ) : (
        <input
          id={id}
          className={cn(
            inputClass,
            (field.kind === "expression" || field.kind === "equation") &&
              "font-mono",
          )}
          value={value}
          disabled={disabled}
          inputMode={field.kind === "number" ? "decimal" : undefined}
          placeholder={field.help || undefined}
          autoComplete="off"
          spellCheck={false}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
      {field.help && field.kind === "choice" && (
        <p className="mt-1 text-xs text-slate-500">{field.help}</p>
      )}
    </div>
  );
}

export function PracticeSession() {
  const withToken = useWithToken();
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [objectives, setObjectives] = useState<Record<string, Objective>>({});
  const [templateId, setTemplateId] = useState("");
  const [scenarioId, setScenarioId] = useState("");
  const [instance, setInstance] = useState<QuestionInstance | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [hintsUsed, setHintsUsed] = useState<string[]>([]);
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const startedAt = useRef(0);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      withToken(practiceApi.templates),
      withToken(practiceApi.objectives),
    ])
      .then(([t, o]) => {
        if (cancelled) return;
        setTemplates(t);
        setTemplateId((current) => current || t[0]?.id || "");
        setObjectives(Object.fromEntries(o.map((x) => [x.id, x])));
      })
      .catch((e) => !cancelled && setError(describeApiError(e)));
    return () => {
      cancelled = true;
    };
  }, [withToken]);

  const template = useMemo(
    () => templates.find((t) => t.id === templateId),
    [templates, templateId],
  );

  /** A fresh instance (new seed); a variation keeps the current question's template. */
  async function newQuestion(variationOf?: QuestionInstance) {
    setBusy(true);
    setError(null);
    try {
      const next = await withToken(practiceApi.createInstance, {
        template_id: variationOf?.template_id ?? (templateId || undefined),
        scenario_id: scenarioId || undefined,
      });
      setInstance(next);
      setValues({});
      setHintsUsed([]);
      setResult(null);
      startedAt.current = Date.now();
    } catch (e) {
      setError(describeApiError(e));
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (!instance) return;
    const { response, problems } = buildResponse(
      instance.response_fields,
      values,
    );
    if (problems.length) {
      setError(problems.join(" "));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setResult(
        await withToken(practiceApi.submitAttempt, instance.id, {
          response,
          hints_used: hintsUsed,
          time_taken_ms: Date.now() - startedAt.current,
        }),
      );
    } catch (e) {
      setError(describeApiError(e));
    } finally {
      setBusy(false);
    }
  }

  function tryAgain() {
    setResult(null);
    startedAt.current = Date.now();
  }

  const title = (code: string) => objectives[code]?.title ?? code;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Choose a model</CardTitle>
          <CardDescription>
            Each question assesses specific modelling skills. Spec references
            are to Pearson Edexcel A level Mathematics (9MA0).
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-end">
          <label className="flex-1 text-sm text-slate-300">
            <span className="mb-1.5 block font-medium">Template</span>
            <select
              className={inputClass}
              value={templateId}
              onChange={(e) => {
                setTemplateId(e.target.value);
                setScenarioId("");
              }}
            >
              {templates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.title} (spec {t.spec_refs.join(", ")})
                </option>
              ))}
            </select>
          </label>
          <label className="flex-1 text-sm text-slate-300">
            <span className="mb-1.5 block font-medium">Context</span>
            <select
              className={inputClass}
              value={scenarioId}
              onChange={(e) => setScenarioId(e.target.value)}
            >
              <option value="">Any context</option>
              {template?.scenarios.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.title}
                </option>
              ))}
            </select>
          </label>
          <Button onClick={() => newQuestion()} disabled={busy || !templateId}>
            {busy && !instance ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Shuffle className="size-4" />
            )}
            {instance ? "New question" : "Start"}
          </Button>
        </CardContent>
      </Card>

      {error && (
        <p
          role="alert"
          className="rounded-lg border border-amber-300/30 bg-amber-300/10 px-4 py-3 text-sm text-amber-100"
        >
          {error}
        </p>
      )}

      {instance && (
        <Card className="border-cyan-300/20">
          <CardHeader>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="muted">{instance.scenario.title}</Badge>
              {instance.objectives.map((o) => (
                <Badge key={o.id} variant={o.is_primary ? "default" : "muted"}>
                  {o.id} · {title(o.id)}
                </Badge>
              ))}
            </div>
            <p className="mt-3 text-base leading-7 text-slate-100">
              {instance.prompt}
            </p>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid gap-4 sm:grid-cols-2">
              {instance.response_fields.map((field) => (
                <div
                  key={field.name}
                  className={cn(
                    (field.kind === "choice" ||
                      field.kind === "equation" ||
                      field.kind === "expression") &&
                      "sm:col-span-2",
                  )}
                >
                  <FieldInput
                    field={field}
                    value={values[field.name] ?? ""}
                    disabled={busy || result !== null}
                    onChange={(v) =>
                      setValues((prev) => ({ ...prev, [field.name]: v }))
                    }
                  />
                </div>
              ))}
            </div>

            {instance.hints.length > 0 && (
              <div className="space-y-2">
                {instance.hints.map((hint) =>
                  hintsUsed.includes(hint.id) ? (
                    <p
                      key={hint.id}
                      className="flex gap-2 rounded-lg bg-slate-800/60 px-3 py-2 text-sm text-slate-300"
                    >
                      <Lightbulb className="mt-0.5 size-4 shrink-0 text-amber-200" />
                      {hint.text}
                    </p>
                  ) : null,
                )}
                {hintsUsed.length < instance.hints.length && !result && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      const next = instance.hints.find(
                        (h) => !hintsUsed.includes(h.id),
                      );
                      if (next) setHintsUsed((prev) => [...prev, next.id]);
                    }}
                  >
                    <Lightbulb className="size-4" /> Show a hint
                  </Button>
                )}
              </div>
            )}

            {!result && (
              <Button onClick={submit} disabled={busy}>
                {busy && <Loader2 className="size-4 animate-spin" />}
                Check my answer
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {instance && result && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-4">
              <CardTitle>Feedback</CardTitle>
              <Badge variant={OUTCOME_BADGE[result.outcome]}>
                Attempt {result.attempt_number}: {result.outcome}
              </Badge>
            </div>
            <CardDescription>
              Each step is marked separately and recorded as evidence for its
              objective. Only the structured answers above are marked, not
              free-form working.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <ul className="space-y-3">
              {result.steps.map((s) => (
                <li key={s.step} className="flex gap-3">
                  <OutcomeIcon outcome={s.outcome} />
                  <div className="min-w-0">
                    <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                      {s.objective} · {title(s.objective)}
                    </p>
                    <p className="text-sm text-slate-200">{s.feedback}</p>
                  </div>
                </li>
              ))}
            </ul>

            <div>
              <h3 className="text-sm font-semibold text-slate-200">
                Worked solution
              </h3>
              <ol className="mt-3 space-y-3">
                {result.worked_solution.map((s, i) => (
                  <li
                    key={i}
                    className="rounded-lg border border-slate-800 px-4 py-3"
                  >
                    <p className="text-xs font-medium text-cyan-200">
                      {i + 1}. {s.title}{" "}
                      <span className="text-slate-500">· {s.objective}</span>
                    </p>
                    <p className="mt-1 text-sm leading-6 text-slate-300">
                      {s.text}
                    </p>
                  </li>
                ))}
              </ol>
            </div>

            <div className="flex flex-wrap gap-3">
              <Button variant="outline" onClick={tryAgain} disabled={busy}>
                <RefreshCw className="size-4" /> Try this question again
              </Button>
              <Button onClick={() => newQuestion(instance)} disabled={busy}>
                <Shuffle className="size-4" /> Try a variation
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
