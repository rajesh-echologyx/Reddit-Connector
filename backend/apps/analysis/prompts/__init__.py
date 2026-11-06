"""Versioned prompt templates for AI tasks."""

from __future__ import annotations

from pathlib import Path

PROMPTS_ROOT = Path(__file__).resolve().parent
PROMPT_VERSION = "v1"


def load_prompt(name: str, version: str = PROMPT_VERSION) -> str:
    path = PROMPTS_ROOT / version / name
    return path.read_text(encoding="utf-8").strip()
