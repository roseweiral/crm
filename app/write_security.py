"""Explicit browser-origin and custom-header protection for JSON resource writes."""

import os
from urllib.parse import urlsplit

from fastapi import Header, HTTPException, Request


def allowed_origins() -> list[str]:
    origins = [
        value.strip()
        for value in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
        if value.strip()
    ]
    for origin in origins:
        parsed = urlsplit(origin)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
            or "*" in origin
        ):
            raise RuntimeError("CORS_ORIGINS must contain exact HTTP(S) origins")
    return origins


def require_write(
    origin: str | None = Header(
        default=None, description="Exact configured frontend origin."
    ),
    x_crm_csrf: str | None = Header(
        default=None, description="Must equal 1 for contact writes."
    ),
) -> None:
    """Origin/CSRF check shared by every write, including bodyless ones (DELETE)."""
    if origin not in allowed_origins() or x_crm_csrf != "1":
        raise HTTPException(
            status_code=403, detail="Write origin or CSRF header is invalid"
        )


def require_json_write(
    request: Request,
    origin: str | None = Header(
        default=None, description="Exact configured frontend origin."
    ),
    x_crm_csrf: str | None = Header(
        default=None, description="Must equal 1 for contact writes."
    ),
) -> None:
    require_write(origin, x_crm_csrf)
    if (
        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        != "application/json"
    ):
        raise HTTPException(
            status_code=415, detail="Content-Type must be application/json"
        )
