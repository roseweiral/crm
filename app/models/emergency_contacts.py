"""Contact emergency contact API models.

See documents/api-contract.md "Emergency contact".
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

RelationshipText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        strict=True,
        pattern=r"^[^\x00-\x1f\x7f]+$",
    ),
]


class ContactEmergencyContact(BaseModel):
    id: UUID
    contact_id: UUID
    emergency_contact_id: UUID
    priority: int
    relationship: str


class ContactEmergencyContactDetail(ContactEmergencyContact):
    created_at: datetime
    modified_at: datetime


class ContactEmergencyContactPage(BaseModel):
    items: list[ContactEmergencyContact]
    page: int
    page_size: int
    total: int


class ContactEmergencyContactCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_id: UUID
    emergency_contact_id: UUID
    priority: int = Field(ge=1)
    relationship: RelationshipText

    @model_validator(mode="after")
    def not_your_own_emergency_contact(self) -> "ContactEmergencyContactCreate":
        if self.contact_id == self.emergency_contact_id:
            raise ValueError("contact_id and emergency_contact_id must differ")
        return self


class ContactEmergencyContactPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Defaults permit omission but the nonnullable annotations reject explicit null.
    # default_factory avoids advertising a null default in OpenAPI.
    emergency_contact_id: UUID = Field(default_factory=lambda: None)
    priority: int = Field(default_factory=lambda: None, ge=1)
    relationship: RelationshipText = Field(default_factory=lambda: None)

    @model_validator(mode="after")
    def require_changes(self) -> "ContactEmergencyContactPatch":
        if not self.model_fields_set:
            raise ValueError("At least one editable field is required")
        return self
