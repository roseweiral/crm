"""Contact API response models."""

from datetime import datetime
from enum import Enum
from typing import Annotated
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)


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


class ContactDetail(Contact):
    created_at: datetime
    modified_at: datetime


class ContactPage(BaseModel):
    items: list[Contact]
    page: int
    page_size: int
    total: int


# Input models are separate from response models so server-managed fields cannot
# become editable when the response gains new fields.
ContactName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        strict=True,
        pattern=r"^[^\x00-\x1f\x7f]+$",
    ),
]
NormalizedEmail = Annotated[EmailStr, AfterValidator(lambda value: value.lower())]


class ContactCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: ContactName
    last_name: ContactName
    email: NormalizedEmail | None = None
    status: ContactStatus = ContactStatus.ACTIVE


class ContactPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Defaults permit omission but the nonnullable annotations reject explicit null.
    # default_factory avoids advertising a null default in OpenAPI.
    first_name: ContactName = Field(default_factory=lambda: None)
    last_name: ContactName = Field(default_factory=lambda: None)
    email: NormalizedEmail | None = None
    status: ContactStatus = Field(default_factory=lambda: None)

    @model_validator(mode="after")
    def require_changes(self) -> "ContactPatch":
        if not self.model_fields_set:
            raise ValueError("At least one editable field is required")
        return self
