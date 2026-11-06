# Testing

## Backend

```bash
cd backend
pip install -r requirements-dev.txt
DJANGO_ENV=test python -m pytest tests/
```

Or from the repo root: `make test` (backend pytest + frontend production build).

### Focus areas (Phase 6)

| Area | Tests |
|------|-------|
| DailyStat rollup correctness | `tests/test_analytics.py` |
| Summary/funnel API vs DB | `tests/test_analytics.py` |
| Log redaction | `tests/test_analytics.py` |
| Production settings refuse fixture mode | `tests/test_production_settings.py` |
| Auth login throttle | `tests/test_auth_throttle.py` |

Earlier phases cover auth, Reddit OAuth/fixtures, AI pipeline, review state machine, and Celery automation under `backend/tests/`.

## Frontend

```bash
cd frontend
npm ci
npm run build
npm run lint
```

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs backend pytest and frontend build on pull requests.

Optional dependency audit (not blocking CI yet):

```bash
cd backend && pip install pip-audit && pip-audit -r requirements.txt
cd frontend && npm audit --omit=dev
```
