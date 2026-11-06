# Security checklist

Signed off for Phase 6 production hardening. Re-verify on each deploy.

| Item | Status | Notes |
|------|--------|-------|
| Secrets in env / secret manager; `.env` gitignored; `.env.example` placeholders only | ✓ | See `.env.example` |
| Reddit tokens Fernet-encrypted at rest (`TOKEN_ENCRYPTION_KEY`) | ✓ | Required in production settings |
| OpenAI key server-side only | ✓ | Never sent to SPA |
| Django `SECRET_KEY` unique; insecure placeholders refused in production | ✓ | `config/settings/production.py` |
| HTTPS / secure cookies in production | ✓ | `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, HSTS |
| CORS allowlist only; no `*` with credentials | ✓ | Production raises if `*` present |
| CSRF enabled; SPA reads CSRF cookie | ✓ | Session auth |
| Session cookies `HttpOnly`, `Secure` (prod), `SameSite=Lax` | ✓ | |
| Auth rate limits (login / bootstrap) | ✓ | DRF throttles + nginx `limit_req` on login |
| API default deny (`IsAuthenticated`) except health/login/callback/csrf/bootstrap | ✓ | |
| `ALLOW_BOOTSTRAP` false in production once owner exists | ✓ | Compose prod default false |
| Reddit writes default disabled; approve ≠ publish | ✓ | `REDDIT_SUBMIT_ENABLED=false` |
| PII / logs: redact tokens & Authorization headers | ✓ | `RedactSecretsFilter` |
| Dependency audit available (`pip audit` / `npm audit`) | ✓ | Documented in `docs/TESTING.md` |
| DB least privilege; no public Postgres port in prod compose | ✓ | `ports: !reset []` |
| Fixture mode hard-fail in production | ✓ | Boot `ImproperlyConfigured` |
| Django admin behind auth | ✓ | Restrict further if unused |

## Operational reminders

- Rotate `TOKEN_ENCRYPTION_KEY` only with a re-encrypt plan for stored Reddit tokens.
- Keep `REDDIT_MODE=live` in production.
- Prefer terminating TLS at the edge and setting `SECURE_SSL_REDIRECT=true`.
