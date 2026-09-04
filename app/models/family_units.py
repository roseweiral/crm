"""Family-unit API response models."""

from enum import Enum
from uuid import UUID

from pydantic import BaseModel


class FamilyRelationship(str, Enum):
    CHILD = "child"
    PARENT = "parent"
    GUARDIAN = "guardian"
    OTHER = "other"


class FamilyUnit(BaseModel):
    id: UUID


class FamilyMember(BaseModel):
    contact_id: UUID
    first_name: str
    last_name: str
    relationship: FamilyRelationship


class FamilyUnitDetail(FamilyUnit):
    members: list[FamilyMember]


class FamilyUnitPage(BaseModel):
    items: list[FamilyUnit]
    page: int
    page_size: int
    total: int
