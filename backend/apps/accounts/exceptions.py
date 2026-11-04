"""Unified API error shape: {detail, code, errors}."""

from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    response = exception_handler(exc, context)
    if response is None:
        return None

    data = response.data
    detail: Any = data
    errors: dict[str, Any] | None = None
    code = getattr(getattr(exc, "default_code", None), "value", None) or getattr(
        exc, "default_code", "error"
    )

    if isinstance(data, dict):
        if "detail" in data and len(data) == 1:
            detail = data["detail"]
        else:
            detail = data.get("detail", "Request failed.")
            errors = {k: v for k, v in data.items() if k != "detail"}
            if not errors:
                errors = None
    elif isinstance(data, list):
        detail = data[0] if len(data) == 1 else data

    payload: dict[str, Any] = {
        "detail": detail,
        "code": str(code) if code else "error",
    }
    if errors is not None:
        payload["errors"] = errors

    response.data = payload
    if response.status_code is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
    return response
