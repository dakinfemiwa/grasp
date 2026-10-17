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

## Quality checks

```powershell
npm run lint
npm run build
cd backend
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m alembic check
```
