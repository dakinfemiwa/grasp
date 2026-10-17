// Thin client for the Grasp FastAPI backend. All backend calls go through apiFetch.

const apiUrl = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

/** Mirrors the backend's {"error": {"code", "message", "details"?}} shape. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type ApiFetchOptions = Omit<RequestInit, "body"> & {
  /** Clerk session token, sent as a Bearer token. */
  token?: string | null;
  body?: unknown;
};

export async function apiFetch<T>(
  path: string,
  { token, body, headers, ...init }: ApiFetchOptions = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiUrl}/api/v1${path}`, {
      cache: "no-store",
      ...init,
      headers: {
        ...(body !== undefined && { "Content-Type": "application/json" }),
        ...(token && { Authorization: `Bearer ${token}` }),
        ...headers,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "The Grasp API is unreachable.");
  }

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const error = payload?.error;
    throw new ApiError(
      response.status,
      error?.code ?? "HTTP_ERROR",
      error?.message ?? `Request failed with status ${response.status}.`,
      error?.details,
    );
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export type HealthResponse = {
  status: string;
  service: string;
  database: string;
};

export function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/health");
}

// --- Practice API (all require a Clerk session token) ------------------------------

export type ReviewStatus = "draft" | "reviewed" | "approved";
export type StepOutcome = "correct" | "incorrect" | "missing";
export type EvidenceOutcome = "correct" | "partial" | "incorrect";
export type FieldKind =
  | "choice"
  | "expression"
  | "equation"
  | "number"
  | "number_list";

export type Objective = {
  id: string;
  title: string;
  description: string;
  domain_area: string;
  success_criteria: string[];
  prerequisites: string[];
  domains: string[];
  evidence_types: string[];
  spec_refs: string[];
  catalogue_version: number;
};

export type ScenarioSummary = {
  id: string;
  version: number;
  title: string;
  presentation: string;
  review_status: ReviewStatus;
};

export type TemplateSummary = {
  id: string;
  version: number;
  title: string;
  domain: string;
  primary_objective: string;
  secondary_objectives: string[];
  spec_refs: string[];
  review_status: ReviewStatus;
  scenarios: ScenarioSummary[];
};

export type ResponseField = {
  name: string;
  label: string;
  kind: FieldKind;
  help: string;
  options: string[];
  unit: string | null;
};

export type QuestionInstance = {
  id: number;
  template_id: string;
  template_version: number;
  scenario: ScenarioSummary;
  prompt: string;
  difficulty: number;
  objectives: { id: string; is_primary: boolean }[];
  response_fields: ResponseField[];
  hints: { id: string; objective: string; text: string }[];
};

export type StructuredResponse = Record<string, string | number | number[]>;

export type AttemptResult = {
  evidence_id: number;
  attempt_number: number;
  outcome: EvidenceOutcome;
  steps: {
    step: string;
    objective: string;
    outcome: StepOutcome;
    feedback: string;
  }[];
  objective_outcomes: Record<string, StepOutcome>;
  expected_answer: Record<string, unknown>;
  worked_solution: { objective: string; title: string; text: string }[];
};

export type EvidenceSummary = {
  note: string;
  total_attempts: number;
  objectives: {
    id: string;
    title: string;
    correct: number;
    incorrect: number;
    missing: number;
    last_outcome: StepOutcome | null;
    last_at: string | null;
  }[];
  recent: {
    evidence_id: number;
    instance_id: number;
    template_id: string;
    template_title: string;
    scenario_title: string;
    attempt_number: number;
    outcome: EvidenceOutcome;
    created_at: string;
  }[];
};

export const practiceApi = {
  objectives: (token: string | null) =>
    apiFetch<Objective[]>("/objectives", { token }),
  templates: (token: string | null) =>
    apiFetch<TemplateSummary[]>("/templates", { token }),
  createInstance: (
    token: string | null,
    body: { template_id?: string; scenario_id?: string; seed?: number },
  ) =>
    apiFetch<QuestionInstance>("/practice/instances", {
      method: "POST",
      token,
      body,
    }),
  submitAttempt: (
    token: string | null,
    instanceId: number,
    body: {
      response: StructuredResponse;
      hints_used: string[];
      time_taken_ms?: number;
    },
  ) =>
    apiFetch<AttemptResult>(`/practice/instances/${instanceId}/attempts`, {
      method: "POST",
      token,
      body,
    }),
  evidenceSummary: (token: string | null) =>
    apiFetch<EvidenceSummary>("/practice/evidence/summary", { token }),
};

/** Human-readable text for an ApiError, including 422 field details. */
export function describeApiError(error: unknown): string {
  if (!(error instanceof ApiError)) return "Something went wrong.";
  if (error.code === "VALIDATION_ERROR" && Array.isArray(error.details)) {
    return (error.details as { loc: (string | number)[]; message: string }[])
      .map((d) => `${d.loc.slice(2).join(".") || d.loc.join(".")}: ${d.message}`)
      .join("; ");
  }
  return error.message;
}
