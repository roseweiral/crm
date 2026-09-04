"""Contact role/group assignment API response models."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel


class ContactRoleGroup(BaseModel):
    id: UUID
    contact_id: UUID
    role_type_id: UUID
    group_id: UUID
    start_date: date
    end_date: date | None


class ContactRoleGroupPage(BaseModel):
    items: list[ContactRoleGroup]
    page: int
    page_size: int
    total: int
