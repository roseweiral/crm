"""Contact API response models."""

from enum import Enum
from uuid import UUID

from pydantic import BaseModel


class ContactStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class Contact(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    email: str | None
    status: ContactStatus
    can_login: bool


class ContactPage(BaseModel):
    items: list[Contact]
    page: int
    page_size: int
    total: int
