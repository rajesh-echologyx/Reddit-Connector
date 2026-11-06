"""Log filters that redact secrets and Authorization headers."""

from __future__ import annotations

import logging
import re

_REDACT_PATTERNS = [
    (re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)\S+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(authorization\s*[:=]\s*)\S+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(access[_-]?token\s*[:=]\s*)\S+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(refresh[_-]?token\s*[:=]\s*)\S+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)\S+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(secret[_-]?key\s*[:=]\s*)\S+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(password\s*[:=]\s*)\S+"), r"\1[REDACTED]"),
    (re.compile(r"sk-[A-Za-z0-9_-]{10,}"), "sk-[REDACTED]"),
]


def redact_text(message: str) -> str:
    redacted = message
    for pattern, replacement in _REDACT_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


class RedactSecretsFilter(logging.Filter):
    """Strip tokens / Authorization headers from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                record.msg = redact_text(record.msg)
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {
                        k: redact_text(v) if isinstance(v, str) else v
                        for k, v in record.args.items()
                    }
                elif isinstance(record.args, tuple):
                    record.args = tuple(
                        redact_text(a) if isinstance(a, str) else a for a in record.args
                    )
        except Exception:
            # Never break logging
            pass
        return True
