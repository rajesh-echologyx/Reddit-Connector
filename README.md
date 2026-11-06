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
| 3 AI integration | This branch — profile, relevance, drafts, mock OpenAI |
| 4+ Review polish / automation | Stubs only (approve ≠ publish) |

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

## Phase 3 API

| Method | Path | Purpose |
|--------|------|---------|
| GET/PATCH | `/api/v1/profile/` | Expertise, tone, constraints, model overrides |
| GET/POST | `/api/v1/writing-samples/` | List/create samples (max 5 active) |
| PATCH/DELETE | `/api/v1/writing-samples/{id}/` | Update/delete |
| GET | `/api/v1/posts/{id}/` | Detail + analysis + drafts |
| POST | `/api/v1/posts/{id}/analyze/` | Enqueue relevance (`OPENAI_MODE`) |
| POST | `/api/v1/posts/{id}/draft/` | Enqueue draft (requires relevant analysis) |
| GET | `/api/v1/review/queue/` | Drafts in `draft`/`in_review` |
| POST | `/api/v1/review/{id}/edit/` | Save `body_edited` |
| POST | `/api/v1/review/{id}/approve/` | Local approve — **does not post** |
| POST | `/api/v1/review/{id}/reject/` | Reject + notes |
| POST | `/api/v1/review/{id}/regenerate/` | New draft; old discarded |
| GET | `/api/v1/review/{id}/export/` | Clipboard text + permalink |

Phase 2 Reddit/monitors endpoints remain under `/api/v1/reddit/`, `/api/v1/monitors/`, `/api/v1/posts/`.

## Layout

```
backend/     Django 5 + DRF + Celery (profiles, analysis, review apps)
frontend/    Vite + React + TS + Tailwind
backend/fixtures/reddit/   Development sample posts
backend/fixtures/openai/   Mock OpenAI JSON responses
backend/apps/analysis/prompts/v1/  Prompt templates
scripts/     wait-for-db, seed-dev
docker-compose.yml
```

## Security notes

- Keep secrets in `.env` (gitignored). `.env.example` has placeholders only.
- Reddit tokens encrypted at rest with Fernet (`TOKEN_ENCRYPTION_KEY`).
- OpenAI key is server-side only.
- `REDDIT_MODE=fixture` is refused when `DJANGO_ENV=production`.
- Approve ≠ publish. No Reddit comment write path.
