"""Documentation browser API models.

See documents/api-contract.md "Documentation browser".
"""

from pydantic import BaseModel


class DocumentSummary(BaseModel):
    id: str
    title: str
    category: str
    path: str


class DocumentPage(BaseModel):
    items: list[DocumentSummary]


class DocumentDetail(BaseModel):
    id: str
    title: str
    category: str
    path: str
    content: str
