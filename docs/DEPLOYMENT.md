# Deployment

Production topology: Postgres + Redis + Django/Gunicorn + Celery worker/beat + nginx (SPA + API proxy).

## Compose production stack

```bash
cp .env.example .env
# Fill production values — see checklist below
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

App listens on **http://localhost:8080** (nginx). Postgres and Redis ports are not published. Django is not exposed on the host.

### Production `.env` checklist

| Variable | Required value |
|----------|----------------|
| `DJANGO_ENV` | `production` |
| `DJANGO_SECRET_KEY` | Unique ≥32 chars (not a placeholder) |
| `TOKEN_ENCRYPTION_KEY` | Fernet key |
| `DJANGO_ALLOWED_HOSTS` | Your hostname(s) |
| `ALLOW_BOOTSTRAP` | `false` after owner exists |
| `REDDIT_MODE` | `live` (fixture refused) |
| `REDDIT_CLIENT_ID` / `SECRET` / `REDIRECT_URI` / `USER_AGENT` | Live Reddit app |
| `OPENAI_MODE` | `live` (with `OPENAI_API_KEY`) or `mock` |
| `CORS_ALLOWED_ORIGINS` / `CSRF_TRUSTED_ORIGINS` / `FRONTEND_ORIGIN` | Exact SPA origin(s) |
| `SECURE_SSL_REDIRECT` | `true` when TLS terminates at the edge |

Boot fails fast if `REDDIT_MODE=fixture` or the secret key is insecure.

## TLS

Terminate TLS at a load balancer / reverse proxy and forward `X-Forwarded-Proto: https`. Django enables secure cookies + HSTS when `DJANGO_ENV=production`. Set `SECURE_SSL_REDIRECT=true` once HTTPS is available.

## Backups

| Data | Suggestion |
|------|------------|
| Postgres | Daily `pg_dump` (or volume snapshots). Retain ≥7 days. |
| Redis | Ephemeral broker/cache — no durable app state required |
| `.env` / secrets | Store in a secret manager; never commit |
| Media | None in v1 (no user uploads beyond DB text) |

Example dump:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db \
  pg_dump -U raddit raddit > backup-$(date +%F).sql
```

Restore into a fresh volume only after verifying the dump.

## Analytics rollups

Celery Beat runs `analytics.rollup_daily_stats` daily at 00:05 UTC. Manual backfill:

```bash
docker compose exec web python manage.py rollup_analytics --days 30
```

## Updates

```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
# migrations run on web start
```

## Never auto-publish

Approve, mark-published, and export paths do **not** post to Reddit. `REDDIT_SUBMIT_ENABLED` defaults false; no Beat/worker path submits comments.
