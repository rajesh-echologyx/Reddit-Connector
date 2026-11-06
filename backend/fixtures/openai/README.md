# OpenAI mock fixtures

Used when `OPENAI_MODE=mock` (default for local/CI) or in unit tests.

| File | Purpose |
|------|---------|
| `relevance_relevant.json` | High-score relevance payload template |
| `relevance_irrelevant.json` | Low-score / skip-draft payload |
| `draft_response.json` | Draft comment template (no invented personal experience) |

Live mode (`OPENAI_MODE=live`) requires `OPENAI_API_KEY` and calls the OpenAI API.
These fixtures are never a production substitute for real model output.
