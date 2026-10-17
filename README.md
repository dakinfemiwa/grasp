# Grasp

Grasp is a student-facing A-level Maths practice platform. Its first learning domain is **Pearson Edexcel A level Mathematics (9MA0) → Pure Mathematics → mathematical modelling, excluding calculus**: linear, quadratic and trigonometric modelling, and interpreting and evaluating models. (Calculus is part of the qualification; it is just outside this first question bank.)

A student picks a modelling task, answers it in structured parts (variables, equation, solutions, interpretation), and gets step-by-step feedback and a worked solution. Each marked step is recorded as evidence against the modelling skill it shows.

> Grasp was previously called Flexa. The Git remote, local folder, Neon project and Clerk application may still carry the old name; see "Renaming the repository" below.

## Architecture

```
Next.js 16 (app/, components/, lib/api.ts)  ──Clerk JWT──▶  FastAPI /api/v1 (backend/app)
                                                               │
             content (YAML, versioned) ──validated──▶  engine (deterministic Python)
             backend/content/objectives                  app/engine/templates/*.py
             backend/content/scenarios                   generator · validation · marking
                                                               │
                                                     Neon Postgres (SQLAlchemy + Alembic)
```

- **Frontend:** Next.js 16, React 19, TypeScript, Tailwind CSS, small UI primitives in `components/ui/`, Clerk for sign-in. Pages: dashboard `/`, `/practice`, `/progress`. All backend calls go through `lib/api.ts` with the Clerk session token.
- **Backend:** FastAPI modular monolith, versioned REST (`/api/v1`), structured errors `{"error": {code, message, details?}}`. Clerk session JWTs are verified server-side (`app/core/auth.py`); the backend never trusts a client-supplied user id.
- **Database:** Neon Postgres via SQLAlchemy 2 and Alembic (pooled URL for the app, direct URL for migrations).
- **No LLM at runtime.** Parameter generation, constraints, solutions, validation and marking are deterministic Python.

### Core concepts (kept separate)

| Concept | Where | Notes |
|---|---|---|
| Learning objective | `backend/content/objectives/modelling.yaml` → `learning_objectives` | MOD-01..MOD-11, Grasp-internal ids (not Edexcel ids); success criteria, prerequisites (a DAG), domains, evidence types, Edexcel `spec_refs` |
| Question template | `backend/app/engine/templates/*.py` (code, no table) | Typed params, constraints, prompt rendering, solution, answer spec, step marking, validation, review status; immutable `(id, version)` |
| Scenario | `backend/content/scenarios/*.yaml` (versioned YAML, no table) | Context + wording slots, explicit compatible template versions, assumptions, narrowing-only parameter bounds, review status |
| Generated instance | `question_instances` + `question_instance_objectives` | Template + scenario ids/versions, seed, parameters, prompt, expected answer, worked solution, validation results, objective tags |
| Student evidence | `student_evidence` + `evidence_objectives` | Structured response, overall + per-step marking, hints used, attempt number, time; per-objective outcome |

`student_progress` (a per-objective rollup table) exists but nothing writes to it yet: Grasp shows evidence counts, not a mastery estimate.

### Templates

| Template | Domain | Edexcel 9MA0 refs | Marked steps (objective) |
|---|---|---|---|
| `QUAD-RECT-AREA` | quadratic | 2.3, OT3.1, OT2.3 | define variables (MOD-02), form equation (MOD-05), solve (MOD-07), reject negative root (MOD-09), interpret (MOD-08) |
| `LIN-TWO-POINT` | linear | 3.1, OT3.2–3.4 | gradient (MOD-07), equation (MOD-05), gradient meaning (MOD-08), prediction (MOD-07), reliability (MOD-10) |
| `TRIG-WHEEL-HEIGHT` | trigonometric | 5.9, 5.7, 2.11, OT3.5 | features (MOD-01), model (MOD-05), solve (MOD-07), times in first revolution (MOD-09), assumption (MOD-04) |

Thirteen scenarios cover gardens, workshops, marquees, sports grounds, taxi fares, °C→°F, phone plans, a cyclist, Ferris and observation wheels and a mill waterwheel. `spec_refs` are references for teachers, not a claim of complete specification coverage.

**Review status.** Templates and scenarios start as `draft`. Only `approved` content is served outside `ENVIRONMENT=development`. Every item is currently `draft`: a teacher must review it before production. **Set `ENVIRONMENT=production` when deploying**, because the default is `development`.

## Run locally

```powershell
npm install
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Configure `backend/.env` (or the repo-root `.env` written by `neon env pull`) and `.env.local`; see `.env.example` and `backend/.env.example` (`DATABASE_URL`, optional `DATABASE_URL_UNPOOLED`, `FRONTEND_URL`, `CLERK_ISSUER`; `NEXT_PUBLIC_API_URL`, Clerk keys). Then, from `backend/`:

```powershell
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m app.seed            # sync the objective catalogue
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

In a second terminal, from the repository root: `npm run dev`, then open `http://localhost:3000`.

## Generating questions

From `backend/`:

```powershell
.venv\Scripts\python.exe -m app.engine.cli list                                   # templates and their scenarios
.venv\Scripts\python.exe -m app.engine.cli generate QUAD-RECT-AREA --count 20 --show
.venv\Scripts\python.exe -m app.engine.cli generate LIN-TWO-POINT --scenario SCN-LIN-TEMPERATURE --count 20
.venv\Scripts\python.exe -m app.engine.cli generate TRIG-WHEEL-HEIGHT --count 20 --save   # persist to the DB
```

Each instance is a pure function of (template id + version, scenario id + version, seed). Generation picks independent values and derives dependent ones, so a clean, valid solution is guaranteed. Every instance must pass all validation checks before it is used, otherwise generation raises.

API under `/api/v1` (Clerk token required): `GET /objectives`, `GET /templates`, `POST /practice/instances` (`template_id`, `scenario_id`, `seed` all optional), `GET /practice/instances/{id}`, `POST /practice/instances/{id}/attempts`, `GET /practice/evidence/summary`.

## Adding a template

1. Create `backend/app/engine/templates/<name>.py` with a subclass of `QuestionTemplate[Params, Slots, Response]` (`app/engine/base.py`):
   - Pydantic models: strict `Params` (sampled fields need `ge`/`le`; mark dependent ones `json_schema_extra={"derived": True}`), `Slots` (scenario wording) and `Response` (the structured answer);
   - `constraints`, `marking_criteria` (step → objective), `response_fields`, optional `hints`, `spec_refs`, `default_scenario`;
   - methods `sample(rng, bounds)`, `render_prompt`, `expected_answer`, `worked_solution`, `mark`, `difficulty`, and optional `fields(slots)` and `checks` (template-specific validation).
2. Decorate it with `@register` and import it in `app/engine/templates/__init__.py`.
3. Add at least one scenario that lists it under `compatible_templates`.
4. Add tests modelled on `tests/test_quadratic_template.py`, and run the CLI for 20+ seeds per scenario.
5. Never change a published `(id, version)`; bump `version` instead, so stored instances stay reproducible.

The generic pipeline rejects a template whose expected answer isn't marked fully correct, whose objectives aren't in the catalogue, or whose marking doesn't assess its primary objective.

## Adding a scenario

Add an entry to a YAML file in `backend/content/scenarios/`: id `SCN-…`, version, description, entities, relationships, assumptions, presentation, `review_status`, and for each compatible template version its `slots` and optional `bounds`. The library is validated at load against the template registry: slots must fit the template's `Slots` model, and bounds may only narrow parameter ranges. Wording must not reveal the model or a solution; the per-template checks enforce this for each generated prompt.

## Quality checks

```powershell
npm run lint
npx tsc --noEmit
npm run build
cd backend
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m alembic check
```

## Renaming the repository

The GitHub repository is still `dakinfemiwa/flexa`. Renaming it is a manual step:

1. On GitHub: `dakinfemiwa/flexa` → Settings → Repository name → `grasp`. GitHub redirects the old URL in the meantime.
2. Locally: `git remote set-url origin https://github.com/dakinfemiwa/grasp.git`
3. Optional: rename the Clerk application and Neon project display names (keys and connection strings are unaffected).
