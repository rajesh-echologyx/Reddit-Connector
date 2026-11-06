# Setup

## Prerequisites

- Docker + Docker Compose v2
- Or: Python 3.12+, Node 22+, Postgres 16, Redis 7

## Local (Docker)

```bash
cp .env.example .env
# Set at least DJANGO_SECRET_KEY and TOKEN_ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| API | http://localhost:8000 |
| Health | http://localhost:8000/api/v1/health/ |

1. Open the login page → **First-run bootstrap** (`ALLOW_BOOTSTRAP=true`, zero users).
2. Optionally seed fixture Reddit posts:

```bash
docker compose exec web python manage.py seed_dev_reddit --poll
```

3. Fill **Profile** (expertise / constraints), create a **Monitor**, run it, then work the **Review** queue.
4. Open **Analytics** for 7d/30d funnel counters (from DB rollups).

## Hard invariants

- Never auto-publish Reddit comments. Approve is local only.
- Official Reddit API only (`REDDIT_MODE=live` or fixture for development).
- `REDDIT_MODE=fixture` is refused when `DJANGO_ENV=production`.

## Environment checklist

See [`.env.example`](../.env.example) for the full variable list. Minimum for local:

| Variable | Notes |
|----------|-------|
| `DJANGO_SECRET_KEY` | Any long random string |
| `TOKEN_ENCRYPTION_KEY` | Fernet key (even in fixture mode if you later connect OAuth) |
| `ALLOW_BOOTSTRAP` | `true` until the owner account exists |
| `REDDIT_MODE` | `fixture` locally; `live` needs Reddit app credentials |
| `OPENAI_MODE` | `mock` locally/CI; `live` needs `OPENAI_API_KEY` |

## Makefile helpers

```bash
make up
make test
make seed-reddit
make migrate
```
