"""HTTP contract tests for the documentation browser endpoints.

See documents/api-contract.md "Documentation browser" for the full
contract. The manifest itself (which documents exist, under which id) is an
implementation detail behind that contract, not something these contract
tests re-assert item-by-item — only the regression test below, which
protects the manifest/mount pairing itself, imports it directly.
"""

from urllib.parse import quote

import httpx
import pytest

from .support import API_URL


pytestmark = pytest.mark.contract


KNOWN_CATEGORIES = {
    "Overview",
    "Architecture and process",
    "Authentication and authorization",
    "API and testing",
    "Data",
    "Deployment",
}


def test_documents_list_requires_a_session():
    with httpx.Client() as client:
        response = client.get(f"{API_URL}/api/v1/documents", timeout=5)
    assert response.status_code == 401


def test_documents_list_returns_the_manifest(person, session_token):
    _, account = person()
    response = httpx.get(
        f"{API_URL}/api/v1/documents",
        cookies={"crm_session": session_token(account["id"])},
        timeout=5,
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) > 10
    ids = [item["id"] for item in items]
    assert len(ids) == len(set(ids)), "document ids must be unique"
    for item in items:
        assert set(item) == {"id", "title", "category", "path"}
        assert item["category"] in KNOWN_CATEGORIES
        assert item["path"]
    assert "way-of-working" in ids


def test_documents_list_ordered_by_category_then_title(person, session_token):
    _, account = person()
    response = httpx.get(
        f"{API_URL}/api/v1/documents",
        cookies={"crm_session": session_token(account["id"])},
        timeout=5,
    )
    items = response.json()["items"]
    keys = [(item["category"], item["title"]) for item in items]
    assert keys == sorted(keys)


def test_documents_detail_requires_a_session():
    with httpx.Client() as client:
        response = client.get(f"{API_URL}/api/v1/documents/way-of-working", timeout=5)
    assert response.status_code == 401


def test_documents_detail_returns_content(person, session_token):
    _, account = person()
    response = httpx.get(
        f"{API_URL}/api/v1/documents/way-of-working",
        cookies={"crm_session": session_token(account["id"])},
        timeout=5,
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"id", "title", "category", "path", "content"}
    assert body["id"] == "way-of-working"
    assert body["path"] == "documents/way-of-working.md"
    assert "# Way of working" in body["content"]


def test_documents_list_and_detail_paths_agree(person, session_token):
    """The frontend resolves cross-links by matching a document's own path
    (from the detail response) against every other document's path (from
    the list response) — those two sources must never disagree."""
    _, account = person()
    cookies = {"crm_session": session_token(account["id"])}
    list_response = httpx.get(f"{API_URL}/api/v1/documents", cookies=cookies, timeout=5)
    paths_by_id = {item["id"]: item["path"] for item in list_response.json()["items"]}

    for document_id in ("way-of-working", "root-readme", "api-contract"):
        detail_response = httpx.get(
            f"{API_URL}/api/v1/documents/{document_id}", cookies=cookies, timeout=5
        )
        assert detail_response.json()["path"] == paths_by_id[document_id]


def test_documents_detail_returns_404_for_an_unknown_id(person, session_token):
    _, account = person()
    response = httpx.get(
        f"{API_URL}/api/v1/documents/not-a-real-document",
        cookies={"crm_session": session_token(account["id"])},
        timeout=5,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}


def test_documents_detail_rejects_a_traversal_shaped_id_with_no_slash(person, session_token):
    """A single URL path segment structurally can't contain a raw "/", so a
    slash-bearing traversal string never reaches the route at all (Starlette
    404s it before get_document() runs) — the residual risk this guards is a
    dot-heavy id with no slash reaching the manifest lookup and being treated
    as anything other than an ordinary miss."""
    _, account = person()
    traversal_id = quote("....etcpasswd", safe="")
    response = httpx.get(
        f"{API_URL}/api/v1/documents/{traversal_id}",
        cookies={"crm_session": session_token(account["id"])},
        timeout=5,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}

