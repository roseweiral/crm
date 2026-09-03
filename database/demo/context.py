"""Shared configuration and generated records for demo-data modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from faker import Faker


@dataclass(frozen=True)
class DemoConfig:
    contact_count: int
    family_count: int
    unit_count: int
    random_seed: int
    as_of_date: date


@dataclass
class DemoContext:
    config: DemoConfig
    fake: Faker = field(init=False)
    rows: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    adult_contact_ids: list[UUID] = field(default_factory=list)
    child_contact_ids: list[UUID] = field(default_factory=list)
    family_unit_ids: list[UUID] = field(default_factory=list)
    management_group_ids: list[UUID] = field(default_factory=list)
    unit_group_ids: list[UUID] = field(default_factory=list)
    role_type_ids: dict[str, UUID] = field(default_factory=dict)
    group_type_ids: dict[str, UUID] = field(default_factory=dict)
    award_type_ids: dict[str, UUID] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.fake = Faker("en_GB")
        self.fake.seed_instance(self.config.random_seed)

    def set_rows(self, table: str, rows: list[dict[str, Any]]) -> int:
        self.rows[table] = rows
        return len(rows)

    def stable_uuid(self, entity: str, key: str | int) -> UUID:
        return uuid5(
            NAMESPACE_URL,
            f"volunteer-crm:{self.config.random_seed}:{entity}:{key}",
        )
