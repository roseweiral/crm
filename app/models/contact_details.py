"""Contact phone number and address API models.

See documents/api-contract.md "Contact details: phone numbers and
addresses".
"""

from datetime import date, datetime
from enum import Enum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


class ContactPhoneType(str, Enum):
    MOBILE = "mobile"
    HOME = "home"
    WORK = "work"
    OTHER = "other"


class ContactAddressType(str, Enum):
    HOME = "home"
    WORK = "work"
    OTHER = "other"


# Input models are separate from response models so server-managed fields cannot
# become editable when the response gains new fields.
PhoneNumberText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=32,
        strict=True,
        pattern=r"^[^\x00-\x1f\x7f]+$",
    ),
]
AddressText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=200,
        strict=True,
        pattern=r"^[^\x00-\x1f\x7f]+$",
    ),
]


# --- Phone numbers -----------------------------------------------------------


class ContactPhoneNumber(BaseModel):
    id: UUID
    contact_id: UUID
    phone_type: ContactPhoneType
    number: str
    is_primary: bool
    start_date: date
    end_date: date | None


class ContactPhoneNumberDetail(ContactPhoneNumber):
    created_at: datetime
    modified_at: datetime


class ContactPhoneNumberPage(BaseModel):
    items: list[ContactPhoneNumber]
    page: int
    page_size: int
    total: int


class ContactPhoneNumberCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_id: UUID
    phone_type: ContactPhoneType
    number: PhoneNumberText
    is_primary: bool = False


class ContactPhoneNumberPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Defaults permit omission but the nonnullable annotations reject explicit null.
    # default_factory avoids advertising a null default in OpenAPI.
    phone_type: ContactPhoneType = Field(default_factory=lambda: None)
    number: PhoneNumberText = Field(default_factory=lambda: None)
    is_primary: bool = Field(default_factory=lambda: None)
    end_date: date = Field(default_factory=lambda: None)

    @model_validator(mode="after")
    def require_changes(self) -> "ContactPhoneNumberPatch":
        if not self.model_fields_set:
            raise ValueError("At least one editable field is required")
        return self


# --- Addresses -----------------------------------------------------------


class ContactAddress(BaseModel):
    id: UUID
    contact_id: UUID
    address_type: ContactAddressType
    line1: str
    line2: str | None
    city: str | None
    region: str | None
    postcode: str | None
    country: str | None
    start_date: date
    end_date: date | None


class ContactAddressDetail(ContactAddress):
    created_at: datetime
    modified_at: datetime


class ContactAddressPage(BaseModel):
    items: list[ContactAddress]
    page: int
    page_size: int
    total: int


class ContactAddressCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_id: UUID
    address_type: ContactAddressType = ContactAddressType.HOME
    line1: AddressText
    line2: AddressText | None = None
    city: AddressText | None = None
    region: AddressText | None = None
    postcode: AddressText | None = None
    country: AddressText | None = None


class ContactAddressPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address_type: ContactAddressType = Field(default_factory=lambda: None)
    line1: AddressText = Field(default_factory=lambda: None)
    line2: AddressText | None = None
    city: AddressText | None = None
    region: AddressText | None = None
    postcode: AddressText | None = None
    country: AddressText | None = None
    end_date: date = Field(default_factory=lambda: None)

    @model_validator(mode="after")
    def require_changes(self) -> "ContactAddressPatch":
        if not self.model_fields_set:
            raise ValueError("At least one editable field is required")
        return self
