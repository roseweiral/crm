"""Role-type, group-type, and group API response models."""

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


class Group(NamedReference):
    group_type_id: UUID
    parent_id: UUID | None


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
