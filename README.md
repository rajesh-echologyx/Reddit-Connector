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
| 2 Reddit integration | This branch — OAuth, monitors, fixture mode, posts |
| 3+ AI / review / automation | Not started |

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

Disconnect clears local tokens and best-effort revokes the refresh token. **Approve ≠ publish** — there is no Reddit write path in Phase 2.

## Local development (without Docker)

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DJANGO_ENV=local DJANGO_SECRET_KEY=dev ALLOW_BOOTSTRAP=true REDDIT_MODE=fixture
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

## Phase 2 API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/reddit/oauth/start/` | Authorize URL (or fixture notice) |
| GET | `/api/v1/reddit/oauth/callback/` | Code exchange → encrypted tokens |
| GET | `/api/v1/reddit/status/` | Connection status / username / mode |
| POST | `/api/v1/reddit/disconnect/` | Local revoke (+ best-effort Reddit revoke) |
| GET/POST | `/api/v1/monitors/` | List/create monitors |
| GET/PATCH/DELETE | `/api/v1/monitors/{id}/` | Detail/update/delete |
| POST | `/api/v1/monitors/{id}/run/` | Manual poll (enqueue `poll_monitor`) |
| GET/POST | `/api/v1/monitors/{id}/keywords/` | Keywords CRUD |
| PUT | `/api/v1/monitors/{id}/subreddits/` | Replace subreddit set |
| GET | `/api/v1/posts/` | Discovered posts (`status`, `subreddit`, `q`, `min_score`) |
| GET | `/api/v1/posts/{id}/` | Post detail |

Auth endpoints from Phase 1 remain under `/api/v1/auth/` and `/api/v1/health/`.

## Layout

```
backend/     Django 5 + DRF + Celery (reddit + monitors apps)
frontend/    Vite + React + TS + Tailwind
backend/fixtures/reddit/   Development sample posts
scripts/     wait-for-db, seed-dev
docker-compose.yml
```

## Security notes

- Keep secrets in `.env` (gitignored). `.env.example` has placeholders only.
- Reddit tokens encrypted at rest with Fernet (`TOKEN_ENCRYPTION_KEY`).
- `REDDIT_MODE=fixture` is refused when `DJANGO_ENV=production`.
- Approve ≠ publish. No Reddit comment write path in Phase 2.
