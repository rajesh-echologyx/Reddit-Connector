"""OpenAI client interface with live + mock/fixture implementations."""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from django.conf import settings

from .schemas import DRAFT_JSON_SCHEMA, RELEVANCE_JSON_SCHEMA

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures" / "openai"

# Heuristic keywords that make a fixture post "relevant" in mock mode.
RELEVANT_KEYWORDS = (
    "django",
    "celery",
    "postgres",
    "fastapi",
    "python",
    "docker",
    "redis",
    "oauth",
    "api",
    "backend",
    "react",
    "typescript",
)


class OpenAIClientError(RuntimeError):
    """Raised for OpenAI / mock client failures."""


class OpenAIClient(ABC):
    @abstractmethod
    def complete_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: dict[str, Any],
        schema_name: str,
    ) -> dict[str, Any]:
        """Return a parsed JSON object from the model."""


class MockOpenAIClient(OpenAIClient):
    """Deterministic fixture responses for tests and local OPENAI_MODE=mock."""

    def complete_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: dict[str, Any],
        schema_name: str,
    ) -> dict[str, Any]:
        if schema_name == "relevance":
            return self._relevance(user, model)
        if schema_name == "draft":
            return self._draft(user, model)
        raise OpenAIClientError(f"Unknown schema_name: {schema_name}")

    def _relevance(self, user: str, model: str) -> dict[str, Any]:
        fixture_path = FIXTURES_DIR / "relevance_relevant.json"
        low_path = FIXTURES_DIR / "relevance_irrelevant.json"
        # Only score against the post portion — not the expertise list itself.
        post_portion = user
        split_at = re.search(r"\nExpertise topics:", user, re.I)
        if split_at:
            post_portion = user[: split_at.start()]
        text_l = post_portion.lower()
        matched = [k for k in RELEVANT_KEYWORDS if k in text_l]
        expertise_match = re.search(
            r"Expertise topics:\s*(.+?)(?:\nHard constraints:|\nThreshold:|\Z)",
            user,
            re.S | re.I,
        )
        if expertise_match:
            topics_blob = expertise_match.group(1).lower()
            for topic in re.split(r"[,;\n]", topics_blob):
                topic = topic.strip(" -•\t")
                if topic and topic in text_l and topic not in matched:
                    matched.append(topic)

        if matched:
            raw = json.loads(fixture_path.read_text(encoding="utf-8"))
            raw["matched_expertise"] = matched[:5]
            raw["reasons"] = [
                f"Post discusses {matched[0]}, which matches operator expertise.",
                "Operator can likely add useful technical context.",
            ]
            raw["summary"] = f"Relevant technical discussion involving {matched[0]}."
            raw["relevance_score"] = max(75, min(95, 70 + 5 * len(matched)))
            raw["is_relevant"] = True
            raw["_mock_model"] = model
            return raw

        raw = json.loads(low_path.read_text(encoding="utf-8"))
        raw["_mock_model"] = model
        return raw

    def _draft(self, user: str, model: str) -> dict[str, Any]:
        fixture_path = FIXTURES_DIR / "draft_response.json"
        raw = json.loads(fixture_path.read_text(encoding="utf-8"))
        # Soft guard: if the prompt contains a fabricated-experience trap,
        # ensure needs_human_check is populated and draft stays general.
        if "invent" in user.lower() or "personal experience" in user.lower():
            checks = list(raw.get("needs_human_check") or [])
            if not any("experience" in c.lower() for c in checks):
                checks.append(
                    "Post may seek personal experience not listed in the profile."
                )
            raw["needs_human_check"] = checks
        raw["_mock_model"] = model
        return raw


class LiveOpenAIClient(OpenAIClient):
    """Calls the OpenAI Chat Completions API with JSON schema response format."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.OPENAI_API_KEY
        if not self.api_key:
            raise OpenAIClientError(
                "OPENAI_API_KEY is required when OPENAI_MODE=live."
            )

    def complete_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: dict[str, Any],
        schema_name: str,
    ) -> dict[str, Any]:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise OpenAIClientError(
                "openai package is not installed. pip install openai"
            ) from exc

        client = OpenAI(api_key=self.api_key)
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema_name,
                        "strict": True,
                        "schema": schema,
                    },
                },
                temperature=0.2,
            )
        except Exception as exc:  # noqa: BLE001
            raise OpenAIClientError(str(exc)) from exc

        content = response.choices[0].message.content or ""
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise OpenAIClientError(f"Model returned non-JSON: {content[:200]}") from exc


def get_openai_client() -> OpenAIClient:
    mode = (getattr(settings, "OPENAI_MODE", "mock") or "mock").lower()
    if mode == "live":
        return LiveOpenAIClient()
    return MockOpenAIClient()


def schema_for(name: str) -> dict[str, Any]:
    if name == "relevance":
        return RELEVANCE_JSON_SCHEMA
    if name == "draft":
        return DRAFT_JSON_SCHEMA
    raise OpenAIClientError(f"Unknown schema: {name}")
