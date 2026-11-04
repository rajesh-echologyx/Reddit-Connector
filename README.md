# Raddit Connector

Personal Reddit research & AI reply assistant.

**Hard invariants**

- Never auto-publish Reddit comments — humans approve every reply.
- Official Reddit API (OAuth) only — no scraping.

This repository is a monorepo (`backend/` Django/DRF + `frontend/` Vite/React).

## Phase 1 status

Foundation scaffold: Docker Compose services, custom User + session/CSRF auth, health endpoints, dashboard shell with login and empty nav. Domain features (Reddit OAuth, monitors, AI, review) land in later phases.

## Quick start (Docker)

```bash
cp .env.example .env
# set DJANGO_SECRET_KEY at minimum
docker compose up --build
```

| Service  | URL |
|----------|-----|
| API      | http://localhost:8000 |
| Frontend | http://localhost:5173 |
| Health   | http://localhost:8000/api/v1/health/ |

First run: open the frontend login page and use **First-run bootstrap** (requires `ALLOW_BOOTSTRAP=true` and zero users), or:

```bash
# 1) obtain CSRF cookie
curl -c cookies.txt http://localhost:8000/api/v1/auth/csrf/
# 2) bootstrap owner (replace CSRF token from cookie / response)
curl -b cookies.txt -c cookies.txt \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: <csrftoken>" \
  -d '{"username":"owner","password":"choose-a-strong-password"}' \
  http://localhost:8000/api/v1/auth/bootstrap/
```

## Local development (without Docker)

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DJANGO_ENV=local DJANGO_SECRET_KEY=dev ALLOW_BOOTSTRAP=true REDDIT_MODE=fixture
python manage.py migrate
python manage.py runserver
```

SQLite is used when `DATABASE_URL` is unset. For Postgres/Redis, point `DATABASE_URL` / `REDIS_URL` at running services (or use Compose for just `db` + `redis`).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite proxies `/api` to `http://localhost:8000`.

### Tests

```bash
make test
# or
cd backend && DJANGO_ENV=test python -m pytest tests/
cd frontend && npm run build
```

## Auth API (Phase 1)

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/v1/auth/csrf/` | public |
| POST | `/api/v1/auth/login/` | public |
| POST | `/api/v1/auth/logout/` | session |
| GET | `/api/v1/auth/me/` | session |
| POST | `/api/v1/auth/bootstrap/` | public, gated by `ALLOW_BOOTSTRAP` |
| GET | `/api/v1/health/` | public |
| GET | `/api/v1/health/ready/` | public |

Session cookie + CSRF header (`X-CSRFToken`) for mutating verbs.

## Layout

See the technical plan for the full monorepo map. Top-level:

```
backend/     Django 5 + DRF + Celery
frontend/    Vite + React + TS + Tailwind (+ shadcn-ready)
scripts/     wait-for-db, seed stubs
docker-compose.yml
```

## Security notes

- Keep secrets in `.env` (gitignored). `.env.example` has placeholders only.
- `REDDIT_MODE=fixture` is refused when `DJANGO_ENV=production`.
- Approve ≠ publish. No Reddit write path in Phase 1.
