"""Read-only documentation browser: GET /api/v1/documents[, /{document_id}].

See documents/api-contract.md "Documentation browser". No
AuthorizationService and no database connection: this mirrors GET
/api/v1/me's "just needs to be signed in" shape (authentication.py's
get_current_user, already enforced by the shared `protected` dependency
list in main.py) — there is no further scope to enforce and no CRM data
involved, so involving the policy engine would add nothing.
"""

from fastapi import APIRouter, HTTPException, status

from documents import DOCUMENT_MANIFEST, get_manifest_entry, load_document_content
from models.documents import DocumentDetail, DocumentPage, DocumentSummary

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=DocumentPage)
def get_documents() -> DocumentPage:
    """Return every document in the manifest, ordered by category then title."""
    items = sorted(
        (
            DocumentSummary(id=entry.id, title=entry.title, category=entry.category, path=entry.path)
            for entry in DOCUMENT_MANIFEST
        ),
        key=lambda item: (item.category, item.title),
    )
    return DocumentPage(items=items)


@router.get(
    "/{document_id}",
    response_model=DocumentDetail,
    responses={404: {"description": "Document not found"}},
)
def get_document(document_id: str) -> DocumentDetail:
    """Return one document's content, or 404 if document_id isn't in the manifest."""
    entry = get_manifest_entry(document_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentDetail(
        id=entry.id,
        title=entry.title,
        category=entry.category,
        path=entry.path,
        content=load_document_content(entry),
    )
