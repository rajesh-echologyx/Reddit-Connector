# Reddit development fixtures

JSON samples consumed by `FixtureRedditClient` when `REDDIT_MODE=fixture`.

- Files: `*.json` in this directory (see `sample_posts.json`).
- Shape: Reddit listing-style `{ "posts": [ { "data": { ... } }, ... ] }` or a full listing `{ "data": { "children": [...] } }`.
- Seed: `python manage.py seed_dev_reddit --poll`

These fixtures are for local development and tests only. Production refuses `REDDIT_MODE=fixture`.
