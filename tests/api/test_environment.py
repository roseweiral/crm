"""Smoke tests for the local Docker environment."""

import os

import httpx
import psycopg
import pytest


pytestmark = pytest.mark.smoke


def test_database_is_available() -> None:
    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        assert connection.execute("SELECT 1").fetchone() == (1,)


def test_api_is_available() -> None:
    response = httpx.get(f"{os.environ['API_URL']}/health", timeout=5)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_documents_manifest_is_fully_readable() -> None:
    """Every documents.py manifest entry must resolve to a real, readable
    file under DOCUMENTS_ROOT — cheap insurance against the manifest and the
    compose mounts (compose.yaml / compose.test.yaml, both the `app` and
    `api-tester` services) drifting apart."""
    from documents import DOCUMENT_MANIFEST, DOCUMENTS_ROOT

    assert len(DOCUMENT_MANIFEST) > 10
    for entry in DOCUMENT_MANIFEST:
        resolved = DOCUMENTS_ROOT / entry.path
        assert resolved.is_file(), f"{entry.id} -> {resolved} is not a readable file"
