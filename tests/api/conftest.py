"""Shared authenticated HTTP behavior for API tests."""

import os

import httpx
import pytest


@pytest.fixture(autouse=True)
def authenticated_http_get(monkeypatch: pytest.MonkeyPatch) -> None:
    original_get = httpx.get
    session_token = os.environ.get("AUTH_TEST_SESSION_TOKEN")
    if not session_token:
        return

    def get(*args, **kwargs):
        cookies = dict(kwargs.pop("cookies", {}))
        cookies.setdefault("crm_session", session_token)
        return original_get(*args, cookies=cookies, **kwargs)

    monkeypatch.setattr(httpx, "get", get)
