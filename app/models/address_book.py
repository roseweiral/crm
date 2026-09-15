"""Address book (organisation-wide directory) API models.

See documents/api-contract.md "Organisation-wide address book" and
documents/family-and-directory-design.md for the rules these shapes encode.
"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GroupPathEntry(BaseModel):
    id: UUID
    name: str


class AddressBookGroupRole(BaseModel):
    kind: Literal["group_role"] = "group_role"
    role_type_name: str
    group_id: UUID
    group_name: str
    group_path: list[GroupPathEntry]


class AddressBookAccessRole(BaseModel):
    kind: Literal["access_role"] = "access_role"
    access_role_name: str


AddressBookRole = Annotated[
    AddressBookGroupRole | AddressBookAccessRole, Field(discriminator="kind")
]


class AddressBookEntry(BaseModel):
    contact_id: UUID
    first_name: str
    last_name: str
    email: str | None
    roles: list[AddressBookRole]


class AddressBookPage(BaseModel):
    items: list[AddressBookEntry]
    page: int
    page_size: int
    total: int


class VisibilityGroupRole(BaseModel):
    id: UUID
    kind: Literal["group_role"] = "group_role"
    role_type_name: str
    group_name: str
    hidden_from_directory: bool


class VisibilityAccessRole(BaseModel):
    id: UUID
    kind: Literal["access_role"] = "access_role"
    access_role_name: str
    hidden_from_directory: bool


VisibilityRole = Annotated[
    VisibilityGroupRole | VisibilityAccessRole, Field(discriminator="kind")
]


class DirectoryVisibility(BaseModel):
    hidden_from_directory: bool
    roles: list[VisibilityRole]


class RoleVisibilityPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    hidden_from_directory: bool


class DirectoryVisibilityPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Defaults permit omission but the nonnullable annotations reject explicit
    # null, matching the ContactPatch convention (models/contacts.py).
    hidden_from_directory: bool = Field(default_factory=lambda: None)
    roles: list[RoleVisibilityPatch] = Field(default_factory=lambda: None)

    @model_validator(mode="after")
    def require_changes(self) -> "DirectoryVisibilityPatch":
        if not self.model_fields_set:
            raise ValueError("At least one of hidden_from_directory or roles is required")
        return self
