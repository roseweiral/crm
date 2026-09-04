"""Contact role/group assignment API response models."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class ContactRoleGroup(BaseModel):
    id: UUID
    contact_id: UUID
    contact_first_name: str
    contact_last_name: str
    role_type_id: UUID
    role_type_name: str
    group_id: UUID
    group_name: str
    start_date: date
    end_date: date | None


class ContactRoleGroupDetail(ContactRoleGroup):
    created_at: datetime
    modified_at: datetime


class ContactRoleGroupPage(BaseModel):
    items: list[ContactRoleGroup]
    page: int
    page_size: int
    total: int
