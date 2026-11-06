# Raddit Connector

Personal Reddit research & AI reply assistant.

**Hard invariants**

- Never auto-publish Reddit comments — humans approve every reply.
- Official Reddit API (OAuth) only — no scraping.

This repository is a monorepo (`backend/` Django/DRF + `frontend/` Vite/React).

## Phase status

| Phase | Status |
|-------|--------|
| 1 Foundation | Merged |
| 2 Reddit integration | Merged |
| 3 AI integration | Merged |
| 4 Review workflow | Merged |
| 5 Celery automation | Merged |
| 6 Analytics / production | This branch |

## Quick start (Docker)

```bash
cp .env.example .env
# set DJANGO_SECRET_KEY and TOKEN_ENCRYPTION_KEY at minimum
docker compose up --build
```

| Service  | URL |
|----------|-----|
| API      | http://localhost:8000 |
| Frontend | http://localhost:5173 |
| Health   | http://localhost:8000/api/v1/health/ |

First run: open the frontend login page and use **First-run bootstrap** (requires `ALLOW_BOOTSTRAP=true` and zero users).

Then seed fixture posts (optional, `REDDIT_MODE=fixture`):

```bash
docker compose exec web python manage.py seed_dev_reddit --poll
# or locally: make seed-reddit
```

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/SETUP.md](docs/SETUP.md) | Local setup |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Production compose, TLS, backups |
| [docs/TESTING.md](docs/TESTING.md) | Pytest / frontend / CI |
| [docs/SECURITY.md](docs/SECURITY.md) | Security checklist sign-off |
| [.env.example](.env.example) | Complete environment variable list |

## Analytics (Phase 6)

DailyStat rollups (Beat at 00:05 UTC) power the Analytics page and dashboard 7d strip.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/analytics/summary/?range=7\|30` | Counters + daily series |
| GET | `/api/v1/analytics/funnel/?range=7\|30` | discovered → relevant → drafted → approved |

```bash
docker compose exec web python manage.py rollup_analytics --days 30
```

## Production

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

- nginx SPA + API proxy on port **8080**
- Postgres/Redis not published to the host
- `DJANGO_ENV=production` refuses `REDDIT_MODE=fixture` and insecure secrets
- Auth login throttled (DRF + nginx)

## OpenAI modes (Phase 3)

### Mock mode (default for local / CI)

```bash
OPENAI_MODE=mock
# OPENAI_API_KEY not required
```

- Uses deterministic JSON under `backend/fixtures/openai/`.
- Same code paths as live (tasks → validate → persist).
- Default in tests via `DJANGO_ENV=test`.

### Live mode

```bash
OPENAI_MODE=live
OPENAI_API_KEY=sk-...
OPENAI_RELEVANCE_MODEL=gpt-4o-mini   # optional
OPENAI_DRAFT_MODEL=gpt-4o-mini      # optional; per-user overrides on Profile
RELEVANCE_THRESHOLD=70
```

Key is server-side only — never sent to the frontend.

## Reddit modes

### Fixture mode (default for local / CI)

```bash
REDDIT_MODE=fixture
```

- Uses `FixtureRedditClient` + JSON under `backend/fixtures/reddit/`.
- Auto-creates a `RedditAccount` with `status=dev_fixture`.
- Amber banner in the UI: “Development mode — Reddit API not connected”.
- **Refused** when `DJANGO_ENV=production`.

### Live OAuth mode

1. Create a Reddit “web app” at https://www.reddit.com/prefs/apps  
2. Redirect URI must match `REDDIT_REDIRECT_URI` (default `http://localhost:8000/api/v1/reddit/oauth/callback/`).  
3. Set env:

```bash
REDDIT_MODE=live
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
REDDIT_REDIRECT_URI=http://localhost:8000/api/v1/reddit/oauth/callback/
REDDIT_USER_AGENT=web:raddit-connector:v0.1.0 (by /u/YOUR_USER)
TOKEN_ENCRYPTION_KEY=<fernet-key>
```

4. Generate encryption key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

5. Open **Settings** → Connect Reddit. Scopes requested: `identity`, `read` only (no submit).

Disconnect clears local tokens and best-effort revokes the refresh token. **Approve ≠ publish**.

## Local development (without Docker)

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DJANGO_ENV=local DJANGO_SECRET_KEY=dev ALLOW_BOOTSTRAP=true REDDIT_MODE=fixture OPENAI_MODE=mock
export TOKEN_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
python manage.py migrate
python manage.py runserver
```

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
```

## Celery automation (Phase 5)

Celery Beat schedules keyword monitors and chains discover → analyze → draft into the review queue. **Never auto-publishes.**

| Beat entry | Schedule | Task |
|------------|----------|------|
| `dispatch-due-monitors-every-5-min` | every 5 min | `monitors.dispatch_due_monitors` |
| `refresh-expiring-reddit-tokens-hourly` | hourly (:05) | `reddit.refresh_expiring_tokens` |
| `rollup-daily-stats` | daily 00:05 UTC | `analytics.rollup_daily_stats` |

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/monitors/{id}/pause/` | Pause Beat polling |
| POST | `/api/v1/monitors/{id}/resume/` | Resume (blocked if Reddit token expired) |
| GET | `/api/v1/tasks/` | Recent Celery task runs |
| GET | `/api/v1/tasks/{id}/` | Task run detail |
| GET | `/api/v1/automation/status/` | Dashboard summary + failures |

Per-monitor `auto_analyze` / `auto_draft` (defaults true) and env `MONITOR_AUTO_ANALYZE` / `MONITOR_AUTO_DRAFT` control the chain. Expired Reddit tokens flip account status and skip polls until reconnect.

## Review workflow (Phase 4)

Hard invariant: **approve ≠ publish**. Default path is copy draft + open original Reddit post. Authenticated Reddit submit stays behind `REDDIT_SUBMIT_ENABLED=false` (default) and is not implemented even when the flag is on (returns 501).

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/review/queue/?status=` | Filterable queue (`in_review,draft`, `saved_for_later`, …) |
| GET | `/api/v1/review/{id}/` | Draft detail + post context |
| POST | `/api/v1/review/{id}/edit/` | Save `body_edited` |
| POST | `/api/v1/review/{id}/notes/` | Private operator notes |
| POST | `/api/v1/review/{id}/approve/` | Local approve — **does not post** |
| POST | `/api/v1/review/{id}/reject/` | Reject + notes |
| POST | `/api/v1/review/{id}/save-for-later/` | Park draft outside active queue |
| POST | `/api/v1/review/{id}/reopen/` | Return saved draft to queue |
| POST | `/api/v1/review/{id}/mark-published/` | Record manual publish — **does not post** |
| POST | `/api/v1/review/{id}/regenerate/` | New draft; old discarded |
| GET | `/api/v1/review/{id}/export/` | Clipboard text + permalink |
| POST | `/api/v1/review/{id}/submit/` | Blocked unless flag on; never auto |
| GET | `/api/v1/review/{id}/actions/` | Append-only audit log |

Phase 3 profile/analysis and Phase 2 Reddit/monitors endpoints remain under `/api/v1/`.

## Layout

```
backend/     Django 5 + DRF + Celery (profiles, analysis, review, analytics)
frontend/    Vite + React + TS + Tailwind
deploy/      nginx + production frontend Dockerfile
docs/        Setup, deployment, testing, security
backend/fixtures/reddit/   Development sample posts
backend/fixtures/openai/   Mock OpenAI JSON responses
backend/apps/analysis/prompts/v1/  Prompt templates
scripts/     wait-for-db, seed-dev
docker-compose.yml
docker-compose.prod.yml
```

## Security notes

- Keep secrets in `.env` (gitignored). `.env.example` has placeholders only.
- Reddit tokens encrypted at rest with Fernet (`TOKEN_ENCRYPTION_KEY`).
- OpenAI key is server-side only.
- `REDDIT_MODE=fixture` is refused when `DJANGO_ENV=production`.
- Approve ≠ publish. `REDDIT_SUBMIT_ENABLED` defaults false; no auto-submit path.
- Full checklist: [docs/SECURITY.md](docs/SECURITY.md).
