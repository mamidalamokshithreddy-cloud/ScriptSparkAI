from __future__ import annotations

from typing import Any

import requests


class ExternalServiceError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def parse_json_response(response: requests.Response, service_name: str) -> dict[str, Any]:
    try:
        parsed = response.json()
    except ValueError as exc:
        raise ExternalServiceError(f"{service_name} returned invalid JSON.", response.status_code) from exc

    if not isinstance(parsed, dict):
        raise ExternalServiceError(f"{service_name} returned an unexpected JSON shape.", response.status_code)

    return parsed


def compact_error_text(response: requests.Response, limit: int = 500) -> str:
    text = response.text.strip().replace("\n", " ")
    return text[:limit] if text else f"HTTP {response.status_code}"
