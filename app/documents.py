"""Manifest and file access for the documentation browser.

See documents/api-contract.md "Documentation browser". The manifest is the
sole source of truth for which files are servable: a document id is never
used to build a filesystem path directly, only to look up a fixed entry
here, whose `path` is then resolved against DOCUMENTS_ROOT. An id with no
matching entry is unconditionally not found — this is what makes path
traversal not applicable to this endpoint, rather than something guarded
against per request.

Mirrors README.md's own "Documentation index" table: same categories, same
titles, same grouping. Keep the two in sync when either changes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DOCUMENTS_ROOT = Path(os.environ.get("DOCUMENTS_ROOT", "/reference-docs"))


@dataclass(frozen=True)
class DocumentEntry:
    id: str
    path: str
    title: str
    category: str


DOCUMENT_MANIFEST: tuple[DocumentEntry, ...] = (
    DocumentEntry("root-readme", "README.md", "Volunteer CRM", "Overview"),
    # Architecture and process
    DocumentEntry(
        "project-overview", "documents/project-overview.md", "Project overview", "Architecture and process"
    ),
    DocumentEntry("way-of-working", "documents/way-of-working.md", "Way of working", "Architecture and process"),
    DocumentEntry("open-questions", "documents/open-questions.md", "Open questions", "Architecture and process"),
    DocumentEntry(
        "family-and-directory-design",
        "documents/family-and-directory-design.md",
        "Family and directory design",
        "Architecture and process",
    ),
    DocumentEntry(
        "automated-pr-review", "documents/automated-pr-review.md", "Automated PR review", "Architecture and process"
    ),
    # Authentication and authorization
    DocumentEntry(
        "anada", "documents/AnadA.md", "AuthN/AuthZ design (AnadA)", "Authentication and authorization"
    ),
    DocumentEntry(
        "authorization-architecture",
        "documents/authorization-architecture.md",
        "Authorization architecture",
        "Authentication and authorization",
    ),
    DocumentEntry(
        "authentication-operations",
        "documents/authentication-operations.md",
        "Authentication operations",
        "Authentication and authorization",
    ),
    # API and testing
    DocumentEntry("api-contract", "documents/api-contract.md", "API contract", "API and testing"),
    DocumentEntry(
        "review-contact-writes",
        "documents/reviews/contact-writes.md",
        "Contact-writes review",
        "API and testing",
    ),
    DocumentEntry(
        "review-address-book", "documents/reviews/address-book.md", "Address-book review", "API and testing"
    ),
    DocumentEntry(
        "review-address-book-frontend",
        "documents/reviews/address-book-frontend.md",
        "Address-book frontend review",
        "API and testing",
    ),
    DocumentEntry("tests-readme", "tests/README.md", "Tests README", "API and testing"),
    DocumentEntry("test-fixtures-readme", "tests/fixtures/README.md", "Test fixtures", "API and testing"),
    DocumentEntry("app-readme", "app/README.md", "App README", "API and testing"),
    DocumentEntry("web-readme", "web/README.md", "Web README", "API and testing"),
    # Data
    DocumentEntry("demo-data", "documents/demo-data.md", "Demo data design", "Data"),
    DocumentEntry("seed-data-readme", "database/seed/README.md", "Seed data", "Data"),
    DocumentEntry("database-migrations-readme", "database/migrations/README.md", "Database migrations", "Data"),
    DocumentEntry(
        "demo-data-generators-readme", "database/demo/README.md", "Demo data generators", "Data"
    ),
    # Deployment
    DocumentEntry(
        "test-deployment", "documents/test-deployment.md", "Internet-facing test deployment", "Deployment"
    ),
    DocumentEntry(
        "terraform-readme", "infrastructure/terraform/README.md", "Hetzner Terraform module", "Deployment"
    ),
)

_MANIFEST_BY_ID: dict[str, DocumentEntry] = {entry.id: entry for entry in DOCUMENT_MANIFEST}


def get_manifest_entry(document_id: str) -> DocumentEntry | None:
    return _MANIFEST_BY_ID.get(document_id)


def load_document_content(entry: DocumentEntry) -> str:
    return (DOCUMENTS_ROOT / entry.path).read_text(encoding="utf-8")
