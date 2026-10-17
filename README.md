# Grasp

Grasp is a student-facing adaptive A-level Maths practice platform. Its first learning domain is **Edexcel A-level Mathematics → Pure Mathematics → mathematical modelling (excluding calculus)**: linear, quadratic and trigonometric modelling, and interpreting and evaluating models.

Modelling skills are tracked as observable capabilities in a versioned objective catalogue (`MOD-01`..`MOD-11`, see `backend/content/objectives/modelling.yaml`). These are Grasp-internal IDs, not official Edexcel identifiers.

> Grasp was previously called Flexa. The Git remote, local folder, Neon project and Clerk application may still carry the old name; see `PROGRESS.md` for the manual rename steps.

## Architecture

- **Frontend:** Next.js 16, React 19, TypeScript, Tailwind CSS, shadcn-style UI primitives, Clerk for sign-in
- **Backend:** FastAPI modular monolith with versioned REST endpoints (`/api/v1`) and structured errors
- **Database:** Neon Postgres via SQLAlchemy 2 and Alembic (pooled URL for the app, direct URL for migrations)
- **Auth:** Clerk session JWTs verified by the backend (`get_current_user`); the backend never trusts a client-supplied user ID
- **Content:** YAML files under `backend/content/`, validated and loaded idempotently by `python -m app.seed`

Grasp must use its own Clerk application. Do not reuse keys or issuer domains from another product.

## Run locally

```powershell
npm install
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Configure `backend/.env` (or the repo-root `.env` written by `neon env pull`) and `.env.local`; example files are provided. Then, from `backend/`:

```powershell
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m app.seed
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

In a second terminal, from the repository root:

```powershell
npm run dev
```

Open `http://localhost:3000`. The API health endpoint is `http://localhost:8000/api/v1/health`.

## Question generation

Templates are deterministic Python in `backend/app/engine/templates/` (no LLM at runtime). An instance is a pure function of (template id, template version, seed), and every instance is validated (structural, mathematical, and automated pedagogical/presentation checks) before it can be used.

From `backend/`:

```powershell
.venv\Scripts\python.exe -m app.engine.cli list
.venv\Scripts\python.exe -m app.engine.cli generate QUAD-RECT-AREA --count 20 --seed 1 --show
.venv\Scripts\python.exe -m app.engine.cli generate QUAD-RECT-AREA --count 20 --seed 1 --save   # persist
```

API (Clerk token required): `GET /api/v1/templates`, `POST /api/v1/practice/instances`, `GET /api/v1/practice/instances/{id}`, `POST /api/v1/practice/instances/{id}/attempts`. Attempts take a structured response (variable, other side, equation, roots, final dimensions) and are marked step by step; each step is recorded as objective-level evidence.

Scenarios (`backend/content/scenarios/*.yaml`) supply the context and wording: a scenario lists exactly which template versions it supports, the wording slots for each, and optional bounds that can only narrow a template's parameter ranges. List them with `cli list`; pass `--scenario SCN-…` to `generate`.

Objectives and templates carry `spec_refs`: references to the Pearson Edexcel A level Mathematics (9MA0, Issue 4) content numbers and overarching themes. They help teachers navigate; they are not a claim of complete specification coverage.

Templates and scenarios start as `draft`. Only `approved` templates are served outside `ENVIRONMENT=development`; change `review_status` after a teacher has reviewed the template.

### Adding a template

1. Create `backend/app/engine/templates/<name>.py` with a subclass of `QuestionTemplate` (`app/engine/base.py`): a strict Pydantic params model, a response model, `constraints`, `marking_criteria`, `response_fields`, and the methods `sample`, `render_prompt`, `expected_answer`, `worked_solution`, `mark`, `difficulty` and optionally `checks`. In `sample`, choose independent values and derive the dependent ones so a valid solution is guaranteed.
2. Decorate it with `@register` and import it in `app/engine/templates/__init__.py`.
3. Reference only catalogue objective ids. Validation fails if `expected_answer` is not marked fully correct.
4. Add tests (see `tests/test_quadratic_template.py`), and run the CLI for 20+ seeds.
5. Never change a published `(id, version)`; bump `version` instead, so stored instances stay reproducible.

## Quality checks

```powershell
npm run lint
npm run build
cd backend
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m alembic check
```
