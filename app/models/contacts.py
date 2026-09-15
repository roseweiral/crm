"""Contact API response models."""

from datetime import date, datetime
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
    field_validator,
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
    date_of_birth: date | None
    preferred_name: str | None
    phonetic_name: str | None
    pronouns: str | None
    gender: str | None


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
# Free text, but nullable - unlike ContactName, these five fields may be
# explicitly cleared, so the type stays Optional rather than using the
# hidden-default-rejects-null trick below.
PersonalDetailText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        strict=True,
        pattern=r"^[^\x00-\x1f\x7f]+$",
    ),
]


class ContactCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: ContactName
    last_name: ContactName
    email: NormalizedEmail | None = None
    status: ContactStatus = ContactStatus.ACTIVE


# Fields gated by contact:update - unchanged access since open-questions.md #4.
CORE_CONTACT_FIELDS = frozenset({"first_name", "last_name", "email", "status"})
# Fields gated by contact-personal:update (documents/api-contract.md "Personal details").
PERSONAL_DETAIL_FIELDS = frozenset(
    {"date_of_birth", "preferred_name", "phonetic_name", "pronouns", "gender"}
)


class ContactPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Defaults permit omission but the nonnullable annotations reject explicit null.
    # default_factory avoids advertising a null default in OpenAPI.
    first_name: ContactName = Field(default_factory=lambda: None)
    last_name: ContactName = Field(default_factory=lambda: None)
    email: NormalizedEmail | None = None
    status: ContactStatus = Field(default_factory=lambda: None)
    date_of_birth: date | None = None
    preferred_name: PersonalDetailText | None = None
    phonetic_name: PersonalDetailText | None = None
    pronouns: PersonalDetailText | None = None
    gender: PersonalDetailText | None = None

    @field_validator("date_of_birth")
    @classmethod
    def date_of_birth_not_in_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("date_of_birth must not be in the future")
        return value

    @model_validator(mode="after")
    def require_changes(self) -> "ContactPatch":
        if not self.model_fields_set:
            raise ValueError("At least one editable field is required")
        return self
