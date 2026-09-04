"""Role-type, group-type, and group API response models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class NamedReference(BaseModel):
    id: UUID
    name: str
    description: str | None


class RoleType(NamedReference):
    pass


class GroupType(NamedReference):
    pass


class NamedReferenceDetail(NamedReference):
    created_at: datetime
    modified_at: datetime


class RoleTypeDetail(NamedReferenceDetail):
    pass


class GroupTypeDetail(NamedReferenceDetail):
    pass


class Group(NamedReference):
    group_type_id: UUID
    group_type_name: str
    parent_id: UUID | None
    parent_name: str | None


class GroupDetail(Group):
    created_at: datetime
    modified_at: datetime


class RoleTypePage(BaseModel):
    items: list[RoleType]
    page: int
    page_size: int
    total: int


class GroupTypePage(BaseModel):
    items: list[GroupType]
    page: int
    page_size: int
    total: int


class GroupPage(BaseModel):
    items: list[Group]
    page: int
    page_size: int
    total: int
