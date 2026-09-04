# Attendance Planner

FastAPI and React attendance planner using the GITAM Login → GStudent → GLearn SSO flow.

## Run locally

1. Start MongoDB and copy `backend/.env.example` to `backend/.env`.
2. Set a strong `SECRET_KEY` and a Fernet `CREDENTIAL_ENCRYPTION_KEY` (generate one with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).
3. Run `uvicorn server:app --app-dir app --reload` from `backend` and `npm run dev` from `frontend`.

## Data flow

`POST /login` establishes one requests session across Login, GStudent, and GLearn. `POST /sync/{student_id}` reads GLearn subject JSON and timetable HTML, then upserts only changed normalized records. The dashboard reads MongoDB only.

Collections are scoped by `student_id`:

- `users`: encrypted password, encryption version, login/sync metadata, and adjustment usage.
- `subjects`: current normalized subject attendance, unique by subject code.
- `timetable_slots`: current normalized weekly slots, unique by day/time/subject.
- `planner_results`: latest calculated dashboard projection.
- `sync_history` and `adjustment_log`: small audit records, not attendance snapshots.

Portal cookies, CAPTCHA values, SSO links, and passwords are never returned or logged. Passwords are encrypted at rest so they can be reauthenticated when you manually sync; set the Fernet key before first use and retain it to decrypt existing credentials.

## Deploy (single service: API + UI from one origin)

The backend can serve the built React app, so you deploy **one** container. In that mode `VITE_API_URL` is left unset and the frontend calls the API via a relative (same-origin) path, so no CORS config is needed.

Prerequisites: a MongoDB instance — [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) free cluster is the recommended option.

### Option A — Render (free PaaS)

1. Set the production secrets by copying `backend/.env.production.example` into your Render service env vars (or the `backend/.env` used locally): `DATABASE_URL`, `SECRET_KEY`, `CREDENTIAL_ENCRYPTION_KEY`.
2. Create a new **Web Service** → **Docker** pointing at the repo's `Dockerfile` (or import `render.yaml`, after replacing the repo URL).
3. Render builds the image, injects `$PORT`, and deploys with free HTTPS.

The frontend is served from the same origin and syncs attendance on demand via the **Sync** button. No background scheduler runs; data is only refreshed when you manually trigger a sync.

### Option B — Linux VPS / Docker Compose (always-on)

1. Point `DATABASE_URL` at your Atlas (or self-hosted) MongoDB in `backend/.env`.
2. Run `docker compose up -d --build` — the app serves on port `8000`.
3. Put a reverse proxy (Caddy/Nginx) + TLS in front if you need HTTPS and a domain.

### env var reference

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | MongoDB connection string (required) |
| `SECRET_KEY` | JWT signing secret (required, long & random) |
| `CREDENTIAL_ENCRYPTION_KEY` | Fernet key for stored portal passwords (required before first login) |
| `FRONTEND_DIST` | Where the built UI lives (defaults to `frontend/dist`) |
| `CORS_ORIGINS` | Only needed if the UI and API live on different origins |
| `DATABASE_NAME`, `TOKEN_EXPIRE_HOURS`, `MAX_CUSTOM_ADJUSTMENTS_PER_MONTH`, `PLANNER_CAMPUS`, `PLANNER_TIMEZONE` | Optional tuning (safe defaults) |
