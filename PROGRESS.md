# Grasp (formerly Flexa) MVP — Progress

Tracks progress against `instructions.md`. One section per stage. Stages 0–2 were built against the
old SUVAT/Flexa brief and are kept below as history. `instructions.md` was then rewritten (Grasp,
Pure modelling without calculus); the stage map from Stage 3 on follows §13 of the new brief.

| Stage | Status |
|---|---|
| 0 — Repository audit | ✅ Done (2026-10-17) |
| 1 — Architecture + scaffold | ✅ Done (2026-10-17) — verified against Neon |
| 2 — Data model | ✅ Done (2026-10-17) |
| 3 — Rename to Grasp + modelling objective catalogue | ✅ Done (2026-10-17) — verified against Neon |
| 4 — Quadratic template engine + instance/evidence schema (generation, constraints, worked solution, structured marking, validation, ≥20 instances) | ✅ Done (2026-10-17) — verified against Neon |
| 5a — Edexcel spec refs + scenario library | ✅ Done (2026-10-17) — verified against Neon |
| 5b — Linear template LIN-TWO-POINT (spec 3.1) | ✅ Done (2026-10-17) |
| 5c — Trig template TRIG-WHEEL-HEIGHT (spec 5.9, 5.7, 2.11) | ✅ Done (2026-10-17) |
| 6 — Student UI: modelling practice, structured response, feedback, worked solution, variation | ⏭ Next |
| 7 — Tests sweep, README/architecture docs, final report (+ deployment, if still wanted) | Not started |

**Decision (2026-10-17):** Generation engine, validation and marking live in the **Python backend**
(deterministic, no LLM). This departs from the brief's "TypeScript" wording in favour of its
"reuse existing architecture" rule. SUVAT content is retired (dev seed only; no student data existed).

**Decision (2026-10-17):** Option A approved — FastAPI + PostgreSQL own all app data; Convex removed.

---

## Stage 0 — Repository audit

### What exists

**Frontend (repo root, not `/frontend`)**
- Next.js 16.3.6, React 19.2, TypeScript, Tailwind v4, shadcn-style primitives (`components/ui/*`), lucide icons.
- Clerk (`@clerk/nextjs` v7): `ClerkProvider` in `app/layout.tsx`, sign-in/sign-up routes, `proxy.ts` (Next 16 replacement for middleware) protects `/`.
- `app/page.tsx` (320 lines): dashboard UI, partly static placeholder content.
- `components/practice-panel.tsx`: practice UI wired to Convex.
- `lib/api.ts`: minimal FastAPI client (`getHealth` only), uses `NEXT_PUBLIC_API_URL`.

**Application data: Convex (not in the target architecture)**
- `convex/schema.ts`: `users`, `learningObjectives`, `questions`, `attempts`, `studentObjectiveProgress`.
- `convex/attempts.ts`: marking is done here (`Number()` parse + tolerance) and progress is updated here (mastery = correct/attempted).
- Ownership derived from Clerk identity server-side — good pattern.
- ~300 lines of Convex code in total; a seed with a handful of questions.

**Backend: `backend/` (FastAPI)**
- `app/main.py`, `app/core/config.py` (pydantic-settings), `app/core/errors.py` (generic 500 handler), `app/db/session.py` (SQLAlchemy engine, SQLite default, Postgres via `DATABASE_URL`), `app/api/v1/health.py` (`GET /api/v1/health` with DB `SELECT 1`).
- Alembic configured (`backend/alembic.ini`, `env.py` reads settings) but **no `versions/` directory and no models**.
- CORS allows only `GET` from `FRONTEND_URL`.
- No auth on the backend.

**Tests**
- Backend: `backend/tests/test_health.py` — **1 passed**.
- Frontend: no tests, no test runner installed.

**Checks run**
- `pytest`: 1 passed.
- `npm run lint`: 0 errors, 3 warnings (unused eslint-disable directives).
- `tsc --noEmit`: errors in `convex/*` only — `convex/_generated` is stale relative to `schema.ts` (needs `npx convex dev`). Not worth fixing if Convex is retired.

**Deployment config**: none (no `vercel.json`, `render.yaml`, Dockerfile, CI).

### Problems found
1. **Python virtualenv committed to git** — `backend/.venv` (≈8.5k tracked files) plus `__pycache__/*.pyc`. `.gitignore` has no Python entries.
2. **Stray second venv** at `backend/app/.venv` (different FastAPI version, untracked). Should be deleted.
3. **Split persistence**: app data in Convex, FastAPI only does health. The instructions require marking, error analysis, adaptive engine and analytics in Python over PostgreSQL — those need direct access to attempts/progress/questions. Keeping Convex would mean two sources of truth.
4. Marking logic lives in Convex/TS — must move to the deterministic Python marking engine (Stage 4).
5. README describes the Convex setup; will need rewriting.
6. Secrets: `.env` / `.env.local` contain real Clerk/Convex keys but are correctly gitignored (`.env*`). Not committed. `CLERK_SECRET_KEY` is server-only. OK.

### Recommendation

**Extend the existing project; do not start clean.** The Next.js app, Clerk setup, UI primitives and FastAPI skeleton are all sound and match the target stack.

Changes for Stage 1:
- **Keep** Next.js at repo root (moving it to `/frontend` costs churn and breaks Vercel defaults for no MVP gain). Monorepo layout = root Next.js app + `backend/`.
- **Keep** Clerk. Frontend sends the Clerk session JWT as `Authorization: Bearer`; FastAPI verifies it against Clerk's JWKS (`PyJWT`) and maps `sub` → `users.external_auth_id`. Ownership is always derived from the token, never from a client-supplied id.
- **Retire Convex** — move its schema to SQLAlchemy models + Alembic migrations in Postgres, replace Convex hooks with calls through `lib/api.ts`, then remove `convex/`, `convex` dependency and `ConvexClientProvider`. (Only ~300 lines; the domain model carries over directly.)
- **Keep** FastAPI skeleton; add `/api/v1` routers, POST in CORS, auth dependency, structured error responses.
- **Repo hygiene first**: `git rm -r --cached backend/.venv`, delete `backend/app/.venv`, add Python ignores (`.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `*.db`).
- Local Postgres for dev (Docker `postgres:16` or a local install); SQLite stays only as a test fixture fallback.

### Ready for Stage 1
Audit complete. Stage 1 can begin once the Convex-retirement decision above is confirmed.

---

## Stage 1 — Architecture + scaffold

### Layout
Monorepo: Next.js at repo root (Vercel default), FastAPI in `backend/`.

### Done
**Repo hygiene**
- Untracked both committed virtualenvs (`backend/.venv`, `backend/app/.venv`; ~8.5k files) and `*.pyc`. Deleted the stray `backend/app/.venv`. Added Python entries to `.gitignore`.

**Backend**
- `app/main.py`: `create_app()` factory; CORS from `FRONTEND_URL` (comma-separated), all REST methods, `Authorization`/`Content-Type` headers.
- `GET /health`: process liveness (for Render). `GET /api/v1/health`: also checks the DB (`SELECT 1`), 503 if it's down.
- `app/api/v1/router.py`: single versioned router that new endpoint modules plug into.
- `app/core/config.py`: Postgres default URL; `postgres://` URLs normalised to `postgresql+psycopg://`; `.env` loaded from `backend/` regardless of cwd.
- `app/core/errors.py`: every error is `{"error": {"code", "message", "details"?}}` (HTTP errors, 422 validation, logged 500s).
- Alembic: `alembic.ini` paths now cwd-independent (`%(here)s`); `alembic/versions/` created (first migration comes in Stage 2). Verified `upgrade head` from both repo root and `backend/`.
- `pytest.ini` (no more `PYTHONPATH` needed); tests use in-memory SQLite via `tests/conftest.py`.

**Frontend**
- Convex removed: `convex/`, provider, npm dependency.
- `lib/api.ts`: `apiFetch<T>()` adds the Bearer token, sends JSON, parses structured errors into `ApiError`.
- Routes: `/practice`, `/progress` (placeholders, protected in `proxy.ts`); nav links point to them.
- `components/practice-panel.tsx`: placeholder until Stage 7 (the old Convex practice panel is gone).
- Fixed an existing build break: Clerk v7 removed `<SignedIn>/<SignedOut>`, so these now use `<Show when=…>`.
- `next.config.ts`: `turbopack.root` set (a stray `C:\Users\davea\package-lock.json` confused root detection).

### Checks
- `pytest`: **7 passed** (liveness, DB health, structured 503/404, CORS allow/deny, URL normalisation).
- `tsc --noEmit`: clean. `npm run lint`: clean (0 warnings). `npm run build`: passes.

### Neon (2026-10-17)
- Linked to Neon project `old-recipe-21163133`, branch `production` (`.neon`, gitignored). `neon.ts` declares Postgres only (implicit).
- `neon deploy` / `neon env pull` write `DATABASE_URL` (pooled), `DATABASE_URL_UNPOOLED` (direct), `NEON_BRANCH` to the repo-root `.env`. Backend settings read that file after `backend/.env`, so Neon values win.
- App traffic uses the pooled URL; Alembic uses `DATABASE_URL_UNPOOLED`.
- Verified live: `GET /api/v1/health` → 200 `database: ok` against Neon (PG 18.6), write/read round trip via the app engine, Neon Auth JWKS + `/ok` reachable.
- Neon Auth disabled on `production` (schema kept, not deleted); Clerk remains the auth provider. Re-enable with `auth: true` in `neon.ts` + `neon deploy` if migrating later.

### Notes for later stages
- Clerk JWT verification in FastAPI is deferred to Stage 2, alongside the `User` model.
- README still describes Convex; rewrite at deployment/docs time.
- `.env.local` still has unused `CONVEX_*` / `NEXT_PUBLIC_CONVEX_*` vars; harmless, safe to delete.
- OneDrive can lock `.next` (EPERM on build); `rm -rf .next` fixes it. Consider excluding the folder from sync.

### How to run locally
```powershell
# backend (repo root)
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
backend\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --port 8000
# frontend (second terminal)
npm run dev
```

---

## Stage 2 — Data model

### Schema (`backend/app/models/`, migration `alembic/versions/0001_core_schema.py`)
| Table | Key columns | Notes |
|---|---|---|
| `users` | `id`, `external_auth_id` (unique, Clerk `sub`), `role`, `display_name`, `created_at` | role ∈ student/teacher/admin, default student |
| `learning_objectives` | `id`, `code` (unique slug), `topic`, `name`, `description` | |
| `questions` | `id`, `code` (unique slug), `learning_objective_id` FK, `difficulty` 1–5, `representation`, `context`, `prompt`, `expected_answer`, `tolerance`, `unit`, `explanation`, `metadata` JSONB, `is_active` | CHECKs on difficulty and tolerance |
| `attempts` | `id`, `user_id` FK, `question_id` FK, `submitted_answer`, `parsed_answer`, `correctness`, `error_type`, `time_taken_ms`, `created_at` | index `(user_id, created_at)` for history and analytics |
| `student_progress` | PK `(user_id, learning_objective_id)`, `attempts`, `correct_attempts`, `recent_accuracy`, `estimated_mastery`, `current_difficulty`, `updated_at` | CHECK correct ≤ attempts |

Design choices:
- Enums (`representation`, `correctness`, `error_type`, `role`) are VARCHAR + CHECK, not native PG enums, so adding a value is a simple migration. Python vocab is in `app/models/enums.py`.
- JSON is used only for `questions.metadata` (common-error answers, graph data). Everything queried for analytics is a real column.
- Stable `code` slugs on objectives and questions let content files be re-seeded in place without breaking attempt FKs.
- `attempts` is the source of truth; `student_progress` is a rollup for fast reads.
- A naming convention gives deterministic constraint names. Migration verified with upgrade → downgrade → upgrade on Neon; `alembic check` finds no drift.

### Auth (pulled forward from "Notes for later stages")
- `app/core/auth.py`: verifies Clerk RS256 session tokens against the Clerk JWKS (`CLERK_ISSUER` in `backend/.env`); checks `iss`, `exp`, `sub`, and `azp` ∈ allowed origins.
- `get_current_user` dependency: get-or-create a `User` by `sub` (handles concurrent first requests). The client never supplies a user id.
- `GET /api/v1/me` returns the profile (internal id, role; the Clerk id is not exposed).

### Seed data
- Content lives in `backend/content/suvat.yaml`, separate from code: 5 SUVAT objectives and 3 starter questions (numeric, word, graph).
- `python -m app.seed` (from `backend/`) upserts by `code`; run twice on Neon with stable counts.

### Checks
- `pytest`: **23 passed**: model round-trip, CHECK and FK constraints, seed idempotency/update-in-place, auth (valid token creates the profile once; expired, wrong issuer, wrong azp, missing sub, foreign key and garbage tokens all → 401).
- Live: `/api/v1/me` → structured 401 without a token. A forged token carrying Clerk's real `kid` → 401 (real JWKS fetched, signature rejected).

### Not yet verified
- A real browser-issued Clerk token hitting `/me`. The frontend doesn't call authenticated endpoints until Stage 7 (`useAuth().getToken()` → `apiFetch(..., { token })`).

### Notes
- New deps: `pyjwt[crypto]`, `pyyaml`.
- Repo-root `.env` (Neon) still contains `NEON_AUTH_*` vars. They're unused (Neon Auth is disabled, see Stage 1 › Neon): auth stays on Clerk. Next.js loads this file too, but it has no `NEXT_PUBLIC_` vars, so nothing reaches the browser.
- Teacher role assignment is undecided (Stage 8). The simplest option: an allowlist env var of Clerk ids.

### Ready for Stage 3
Schema, migrations, seed pipeline and content-file format are in place. *(Superseded: the brief changed; see Stage 3.)*

---

## Stage 3 — Rename to Grasp + modelling objective catalogue

### Rename (targeted, not a global replace)
- UI: `app/layout.tsx` metadata ("Grasp | Adaptive maths practice"), `app/page.tsx` brand and copy (SUVAT placeholders → modelling objectives; still static until Stage 6).
- `package.json` name `grasp` (+ lockfile), `lib/api.ts`, `.env.example`, `backend/.env.example`, `backend/alembic/README`.
- Backend: `app_name` "Grasp API", default local DB `grasp`, health `service: grasp-api`, logger `grasp`.
- `README.md` rebranded; stale Convex sections removed (full rewrite in Stage 7).
- **Left unchanged on purpose:** git remote, local folder name, Neon project, Clerk app name (external resources); this file's history; `instructions.md`; your secret files `.env.local` (old Convex comment) and `backend/.env` (local `flexa` DB URL — edit if you use a local Postgres).

### Manual rename steps (external, not done by me)
1. GitHub → `dakinfemiwa/flexa` → Settings → Repository name → `grasp`. GitHub redirects the old URL meanwhile.
2. Then locally: `git remote set-url origin https://github.com/dakinfemiwa/grasp.git`
3. Optional: rename the Clerk application display name in the Clerk dashboard (keys unaffected), and the Neon project name in the Neon console (connection strings unaffected).

### Objective catalogue
- Source of truth: `backend/content/objectives/modelling.yaml` (`catalogue_version: 1`), MOD-01..MOD-11 with title, description, success criteria, prerequisites, domains, evidence types. Labelled as Grasp-internal ids, not Edexcel ids.
- Prerequisites (DAG, 9 edges): 02←01, 03←01, 05←02+03, 07←06, 08←01, 09←01, 10←04, 11←05. Roots: 01, 04, 06.
- Validation: `app/catalogue/schema.py` — Pydantic, `extra="forbid"`, id pattern `^MOD-\d{2}$`, non-empty criteria, enum domains/evidence types; `load_catalogue` adds unique ids, known prerequisites, no self-reference, no cycles, and reports every problem at once.

### Schema (migration `0002_modelling_catalogue`)
- `learning_objectives`: `name`→`title`, `topic`→`domain_area` (index dropped), + `success_criteria`, `domains`, `evidence_types` (JSON), `catalogue_version`.
- New `objective_prerequisites(objective_id, prerequisite_id)`: composite PK, both FKs CASCADE, CHECK not self.
- SUVAT retirement: aborts if any `attempts` exist; otherwise deletes `questions` and `suvat.*` objectives. `questions`/`attempts` tables stay until Stage 4 replaces them.
- Seeder (`python -m app.seed`) now syncs the catalogue: upsert by code, replace prerequisites, delete objectives removed from the file (errors if still referenced). `content/suvat.yaml` deleted.
- `GET /api/v1/objectives` (authenticated) returns the catalogue with prerequisite ids.

### Checks
- `pytest`: **39 passed** (new: catalogue load + 9 rejection cases, sync idempotency, prerequisite change/removal, referenced-delete refusal, self-prereq CHECK, objectives API 401/200).
- Neon: `upgrade head` → `downgrade -1` → `upgrade head` → `alembic check`: no drift. Seed run twice: 11 objectives, 9 prerequisite rows, 0 SUVAT rows, 0 questions.
- Live: `/api/v1/health` → `grasp-api`; `/api/v1/objectives` → 401 without a token.
- Frontend: `tsc --noEmit`, `npm run lint`, clean `npm run build` all pass.

### Notes
- `content/suvat.yaml` had never been committed, so it is **not** in git history. If you want it back, check the OneDrive recycle bin / version history.

### Ready for Stage 4
Objectives exist as FK targets for templates, instances and evidence. Stage 4 adds the quadratic template engine and replaces `questions`/`attempts` with instance/evidence tables.


---

## Stage 4 — Quadratic template engine + instance/evidence schema

### Engine (`backend/app/engine/`, deterministic Python, no LLM)
- `base.py`: `QuestionTemplate` (the extension point for every family), `Constraint`, `MarkingCriterion`, `ResponseField`, `Hint`, `WorkedStep`, `MarkedStep`, `ValidationCheck`, `ReviewStatus`, plus errors (`InvalidParameters`, `GenerationError`, `InvalidInstance`) that each list every problem.
- `generator.py`: `generate(template, seed)` (RNG seeded from `id:vN:seed`, so it's reproducible) and `build(template, params)`. Sampling retries until the constraints hold, then raises. Generic validation covers: registered, objectives exist in the catalogue, marking objectives declared, params typed, constraints hold, primary objective assessed, **expected answer marks fully correct**, worked solution covers criteria, difficulty range.
- `expr.py`: safe single-variable expression/equation parser (whitelisted AST, implicit multiplication, powers ≤ 4) with sample-point equivalence. It is not a CAS.
- `templates/quadratic_rectangle.py`: **QUAD-RECT-AREA v1** (status `draft`). Picks width 2–20 and difference 1–12, derives area (≤ 500 cm²). Primary MOD-05; secondary MOD-02, 07, 09, 08. Template checks: positive solution exists, answer satisfies conditions, negative root rejected by marking, units consistent, given values present, prompt doesn't name x or state a solution.
- Marking has five steps, each tied to one objective: define variables (MOD-02), form equation (MOD-05, any rearrangement/scaling), solve (MOD-07, with follow-through credit for a correctly solved wrong equation), reject the negative root (MOD-09), interpret the dimensions (MOD-08, detects swaps). x = length is accepted as an equally valid model.
- `cli.py`: `python -m app.engine.cli list | generate <ID> --count N --seed S [--show] [--save]`.

### Schema (migration `0003`)
- Dropped the empty `questions` / `attempts` (the migration refuses if they have rows).
- `question_instances`: template id/version, seed, scenario_id (null until Stage 5), parameters, prompt, expected answer, worked solution, validation results, difficulty; unique (template, version, seed).
- `question_instance_objectives`: objective tags with `is_primary`.
- `student_evidence`: user, instance, attempt_number (unique per user+instance), structured response, overall outcome (correct/partial/incorrect), per-step marking, hints used, time taken.
- `evidence_objectives`: per-objective outcome per attempt (correct/incorrect/missing).
- `student_progress` is untouched and separate from evidence. Nothing updates it yet (no mastery estimate), so one wrong answer never "diagnoses" a prerequisite.
- Templates have no table: they're code, and an instance records (id, version, seed) to regenerate exactly.

### API
`GET /templates`, `POST /practice/instances` (`template_id`/`seed` optional; get-or-create), `GET /practice/instances/{id}` (no answer), `POST /practice/instances/{id}/attempts` (marks, stores evidence, returns steps + objective outcomes + worked solution). Bad responses or hint ids → structured 422. Drafts are served only when `ENVIRONMENT=development`.

### Checks
- `pytest`: **105 passed**. New: `test_expr`, `test_engine` (registry, generic validation catches unregistered/misaligned/unknown-objective/unsatisfiable templates), `test_quadratic_template` (brief's 8 × 12 garden, determinism, 30 seeds all valid with ≥ 20 distinct, 8 invalid-param cases, negative root rejected, equivalent equations, length-as-x, construction vs solving vs interpretation separated), `test_practice_api`.
- Neon: `upgrade` → `downgrade -1` → `upgrade` → `alembic check`: no drift. CLI `--save`: 20/20 valid, 20 instances + 100 objective tags stored.
- Live: all practice endpoints → 401 without a token.

### Limitations / notes
- QUAD-RECT-AREA is `draft`: it needs a teacher's review before it's marked `approved` (until then it's served in development only).
- Prompts are plain text with fixed "rectangle, cm" wording; scenarios (garden, sports ground…) come in Stage 5.
- Marking inspects only the structured fields; free-form reasoning isn't assessed.
- No authenticated request from a real browser token has hit the practice endpoints yet (Stage 6 UI).

### Ready for Stage 5
Scenario library with explicit template compatibility, plus linear and trig templates anchored to the Edexcel spec (plan: `~/.claude/plans/good-continue-you-can-bubbly-ocean.md`).

---

## Stage 5a — Edexcel spec references + scenario library

### Spec references
- Source checked: Pearson Edexcel A level Mathematics 9MA0, specification Issue 4 (Feb 2020), from the official PDF.
- Catalogue v2: each objective has `spec_refs` to overarching themes (e.g. MOD-04 → OT3.1, OT3.5; MOD-10 → OT3.4, 2.11). Templates carry `spec_refs` too: QUAD-RECT-AREA → 2.3, OT3.1, OT2.3. These are references for teachers, not a claim of full spec coverage. MOD ids stay Grasp-internal.

### Scenarios (`backend/content/scenarios/*.yaml`)
- Schema in `app/scenarios/schema.py`; cross-checked against the template registry in `app/engine/scenarios.py`. It collects every problem: unknown template/version, slots that don't fit the template's `slots_model`, bounds that widen a template range or name a derived parameter, duplicates, inverted bounds.
- Compatibility is explicit both ways: a scenario lists `{template, version}` with its slots; the template declares the slots it needs (`RectangleSlots`: subject, unit, optional lead-in).
- Library: five rectangle scenarios for QUAD-RECT-AREA — abstract (cm), garden, workshop floor, event marquee, sports-ground training area (m). All `draft`.
- Engine: `generate(template, seed, scenario=None)`. With no scenario, it picks one deterministically from the seed. Scenario bounds narrow sampling. The parameter RNG is unchanged, so the abstract scenario reproduces Stage 4 instances exactly (checked against all 20 stored rows).
- Template API change: `sample(rng, bounds)`, `render_prompt/worked_solution(params, slots)`, `mark(params, slots, response)`, `fields(slots)` (units follow the scenario). New generic checks: `scenario_compatible`, `slots_typed`, `within_scenario_bounds`.

### Schema (migration `0004`)
- `learning_objectives.spec_refs` (JSON).
- `question_instances.scenario_version`; `scenario_id`/`scenario_version` now non-null. The 20 existing rows are backfilled to `SCN-RECT-ABSTRACT` v1 (it aborts if any row can't be backfilled). The unique key is now (template, version, scenario, scenario version, seed). The downgrade refuses if two rows differ only by scenario.
- Found while testing on Neon: after a downgrade, the re-upgrade aborted because `scenario_id` was already set. The guard worked and the transaction rolled back; the backfill condition is fixed.

### API / CLI
- `POST /practice/instances` takes an optional `scenario_id`; the instance includes `scenario`; `GET /templates` lists `spec_refs` and servable scenarios; objectives expose `spec_refs`. Draft scenarios follow the same development-only serving rule as templates.
- `python -m app.engine.cli list` shows scenarios per template; `generate … --scenario SCN-…`.

### Checks
- `pytest`: **131 passed** (new `test_scenarios.py`: library loads; 6 incompatibility + 5 malformed cases; bounds narrow sampling; out-of-bounds params rejected; 20 valid reproducible instances per scenario; deterministic pick covers the library; abstract scenario reproduces stored instances).
- Neon: `upgrade` → `downgrade -1` → `upgrade` → `alembic check`: no drift. Seed: catalogue v2. CLI: 20/20 valid for each scenario. Live: endpoints → 401 without a token.

---

## Stage 5b — Linear template LIN-TWO-POINT v1 (Edexcel 3.1)

- `backend/app/engine/templates/linear_two_point.py`. Two data points in context: find the gradient, form y = mx + c, interpret the gradient, predict, judge reliability (interpolation vs extrapolation). Primary MOD-05; secondary MOD-07, MOD-08, MOD-10. spec_refs 3.1, OT3.2, OT3.3, OT3.4.
- Generation: gradient in tenths, intercept, x₁, gap and an extrapolate flag are sampled. x-values are multiples of a step (10 / gcd(gradient_tenths, 10)), so every y-value is a whole number. y-values are derived.
- Marking (five steps): gradient (detects an inverted Δx/Δy); equation (any rearrangement or scaling of the line, via the new two-variable relation check); gradient meaning (a choice from scenario wording, sorted so position gives nothing away; detects confusion with the intercept); prediction (follow-through from the student's own equation); reliability. MOD-07 aggregates the gradient and prediction steps.
- Template checks: distinct x-values, gradient recoverable from data, wrong reliability judgement is marked incorrect, prompt states exactly the data + prediction point, prompt doesn't name the gradient/intercept.
- Scenarios (`content/scenarios/linear.yaml`, all draft): taxi fares, °C→°F (spec example; fixed at 1.8/32 and interpolation-only, because "extrapolation is less reliable" would mislead for an exact physical law), phone data plan, cyclist at constant speed (spec distance–time example).
- `expr.py` rewritten around a small tokenizer: named variables (`x`, `y`, `t`), implicit multiplication, `compile_relation` + `proportional2` for two-variable equations. All existing parser tests still pass.
- Engine API: `expected_answer(params, slots)` (the right answer can depend on scenario wording).

### Checks
- `pytest`: **162 passed** (new `test_linear_template.py`: docstring example, 20 valid instances per scenario, exact temperature conversion, both reliability cases occur, 7 invalid-param cases, 5 accepted + 4 rejected equation forms, step separation, follow-through, scenario-driven options, slot validation; relation-parser tests; API objective aggregation).
- No schema change (`alembic check` clean). CLI `--save`: 20/20 valid linear instances stored on Neon.

---

## Stage 5c — Trig template TRIG-WHEEL-HEIGHT v1 (Edexcel 5.9, 5.7, 2.11)

- `backend/app/engine/templates/trig_wheel_height.py`: the spec's own example, "the height of a point on a vertical circular wheel". The student extracts the amplitude, centre height and period; forms h(t); solves for every time in the first revolution; states an assumption. Primary MOD-05; secondary MOD-01, MOD-07, MOD-09, MOD-04. spec_refs 5.9, 5.7, 2.11, OT3.5.
- Generation: the period is drawn from divisors of 360 (so k = 360/T is whole), and the target angle from {60°, 90°, 120°} (exact cosines 0.5, 0, −0.5), with angle × T a multiple of 360 so times are whole. The radius is even when cos = ±0.5. The target height and both times are derived.
- Marking (five steps): features (spots radius-vs-centre confusion); model (numeric equivalence in t, so a phase-shifted sine passes; a model starting at the top gets specific feedback); first solution; all solutions in the first revolution (rejects second-revolution and negative times, flags a missing second time); assumption (a choice; the prompt deliberately doesn't say "constant").
- Parser: whitelisted `sin`/`cos` in degrees, opt-in per call (`trig=True`), brackets required.
- Scenarios (`content/scenarios/wheels.yaml`, all draft): Ferris wheel (minutes, default), fairground wheel (seconds), large observation wheel, heritage-mill waterwheel. New `datum` slot: heights can be measured above something other than the ground (the waterwheel pit floor).
- Dropped during authoring: a spun bicycle wheel. Divisor-of-360 periods mean ≥ 4 s per revolution, which isn't realistic for a spun wheel, so it was replaced by the waterwheel (real ones turn at 2–10 rpm). Tides / hours of sunlight (2.11, 5.9) need a different phase and midline, so they're left for a future template.

### Checks
- `pytest`: **201 passed** (new `test_trig_template.py`: docstring example, 20 valid instances per scenario with exact-value checks, all three angles occur, 7 invalid-param cases, 5 accepted + 4 rejected model forms, top-start feedback, extraneous/negative times rejected, missing second time, step separation, scenario units and datum; trig parser tests).
- No schema change (`alembic check` clean). CLI `--save`: 20/20 valid trig instances stored on Neon. The registry now has 3 templates and 13 scenarios.