"""JSON schema validation for OpenAI structured outputs."""

from __future__ import annotations

from typing import Any


class SchemaValidationError(ValueError):
    """Raised when model output fails structural validation."""


ALLOWED_RISK_FLAGS = {
    "off_topic",
    "needs_personal_experience",
    "sensitive",
    "spam_risk",
    "uncertain",
}


def _require_keys(data: dict[str, Any], keys: list[str]) -> None:
    missing = [k for k in keys if k not in data]
    if missing:
        raise SchemaValidationError(f"Missing keys: {', '.join(missing)}")


def _as_str_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise SchemaValidationError(f"{field} must be a list of strings.")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise SchemaValidationError(f"{field} items must be strings.")
        cleaned = item.strip()
        if cleaned:
            out.append(cleaned)
    return out


def validate_relevance_payload(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise SchemaValidationError("Relevance response must be a JSON object.")
    _require_keys(data, ["relevance_score", "is_relevant", "reasons", "matched_expertise"])

    score = data["relevance_score"]
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise SchemaValidationError("relevance_score must be a number 0–100.")
    score_int = int(score)
    if score_int < 0 or score_int > 100:
        raise SchemaValidationError("relevance_score must be between 0 and 100.")

    is_relevant = data["is_relevant"]
    if not isinstance(is_relevant, bool):
        raise SchemaValidationError("is_relevant must be a boolean.")

    reasons = _as_str_list(data.get("reasons"), "reasons")
    matched = _as_str_list(data.get("matched_expertise"), "matched_expertise")
    risk_flags = _as_str_list(data.get("risk_flags"), "risk_flags")
    for flag in risk_flags:
        if flag not in ALLOWED_RISK_FLAGS:
            # Allow unknown flags but keep them for forward-compat; do not reject.
            pass

    summary = data.get("summary", "")
    if summary is None:
        summary = ""
    if not isinstance(summary, str):
        raise SchemaValidationError("summary must be a string.")

    return {
        "relevance_score": score_int,
        "is_relevant": is_relevant,
        "reasons": reasons,
        "matched_expertise": matched,
        "risk_flags": risk_flags,
        "summary": summary.strip(),
    }


def validate_draft_payload(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise SchemaValidationError("Draft response must be a JSON object.")
    _require_keys(data, ["draft"])

    draft = data["draft"]
    if not isinstance(draft, str) or not draft.strip():
        raise SchemaValidationError("draft must be a non-empty string.")

    tone = data.get("tone", "")
    if tone is None:
        tone = ""
    if not isinstance(tone, str):
        raise SchemaValidationError("tone must be a string.")

    claims = _as_str_list(data.get("claims_made"), "claims_made")
    checks = _as_str_list(data.get("needs_human_check"), "needs_human_check")

    return {
        "draft": draft.strip(),
        "tone": tone.strip(),
        "claims_made": claims,
        "needs_human_check": checks,
    }


RELEVANCE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "relevance_score",
        "is_relevant",
        "reasons",
        "matched_expertise",
        "risk_flags",
        "summary",
    ],
    "properties": {
        "relevance_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "is_relevant": {"type": "boolean"},
        "reasons": {"type": "array", "items": {"type": "string"}},
        "matched_expertise": {"type": "array", "items": {"type": "string"}},
        "risk_flags": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
}

DRAFT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["draft", "tone", "claims_made", "needs_human_check"],
    "properties": {
        "draft": {"type": "string"},
        "tone": {"type": "string"},
        "claims_made": {"type": "array", "items": {"type": "string"}},
        "needs_human_check": {"type": "array", "items": {"type": "string"}},
    },
}
