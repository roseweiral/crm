"""Policy-driven authorization service for API decisions and collection scopes."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from psycopg import Connection

from authentication import CurrentUser, get_current_user
from database import get_connection


POLICY_PATH = Path(os.environ.get("AUTHORIZATION_POLICY_PATH", Path(__file__).with_name("policies") / "authorization.toml"))
VALID_SOURCES = {
    "authenticated",
    "access_role",
    "access_role_flag",
    "group_role",
    "family_relationship",
    "main_contact_family",
    "self",
}
VALID_SCOPES = {"all", "group_descendants", "group", "group_and_family", "family", "self"}
SOURCE_SCOPES = {
    "authenticated": {"all"},
    "access_role": {"all"},
    "access_role_flag": {"all"},
    "group_role": {"group_descendants", "group", "group_and_family", "all"},
    "family_relationship": {"family"},
    "main_contact_family": {"family"},
    "self": {"self"},
}
# Flags this policy engine knows how to read off access_roles, rather than
# matching a role by name. "is_global" is the only one so far.
ACCESS_ROLE_FLAGS = {"is_global"}


@dataclass(frozen=True)
class PolicyRule:
    source: str
    relationship: str | None
    scope: str


@dataclass(frozen=True)
class ActionPolicy:
    description: str
    resource: str
    rules: tuple[PolicyRule, ...]


@dataclass(frozen=True)
class AuthorizationPolicy:
    version: int
    actions: dict[str, ActionPolicy]


@dataclass(frozen=True)
class ResourceScope:
    """The complete set of resource identifiers allowed for one action."""

    unrestricted: bool
    ids: frozenset[UUID] = frozenset()

    def contains(self, resource_id: UUID) -> bool:
        return self.unrestricted or resource_id in self.ids


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"Authorization policy field '{field}' must be non-empty text")
    return value.strip()


@lru_cache(maxsize=1)
def load_policy() -> AuthorizationPolicy:
    """Load and validate the human-maintained authorization policy once."""
    try:
        with POLICY_PATH.open("rb") as policy_file:
            document = tomllib.load(policy_file)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise RuntimeError(f"Cannot load authorization policy at {POLICY_PATH}") from error

    if document.get("version") != 1:
        raise RuntimeError("Authorization policy version must be 1")
    raw_actions = document.get("actions")
    if not isinstance(raw_actions, dict) or not raw_actions:
        raise RuntimeError("Authorization policy must define at least one action")

    actions: dict[str, ActionPolicy] = {}
    for action, raw_action in raw_actions.items():
        if not isinstance(raw_action, dict):
            raise RuntimeError(f"Authorization action '{action}' must be a table")
        raw_rules = raw_action.get("rules")
        if not isinstance(raw_rules, list) or not raw_rules:
            raise RuntimeError(f"Authorization action '{action}' must define rules")
        rules: list[PolicyRule] = []
        for raw_rule in raw_rules:
            if not isinstance(raw_rule, dict):
                raise RuntimeError(f"Authorization action '{action}' has an invalid rule")
            source = _required_text(raw_rule.get("source"), f"{action}.rules.source")
            scope = _required_text(raw_rule.get("scope"), f"{action}.rules.scope")
            if source not in VALID_SOURCES:
                raise RuntimeError(f"Authorization action '{action}' uses unknown source '{source}'")
            if scope not in VALID_SCOPES:
                raise RuntimeError(f"Authorization action '{action}' uses unknown scope '{scope}'")
            if scope not in SOURCE_SCOPES[source]:
                raise RuntimeError(
                    f"Authorization action '{action}' cannot combine source "
                    f"'{source}' with scope '{scope}'"
                )
            relationship = raw_rule.get("relationship")
            if source in {"access_role", "access_role_flag", "group_role", "family_relationship"}:
                relationship = _required_text(relationship, f"{action}.rules.relationship")
                if source == "access_role_flag" and relationship not in ACCESS_ROLE_FLAGS:
                    raise RuntimeError(
                        f"Authorization action '{action}' uses unknown access role flag '{relationship}'"
                    )
            elif relationship is not None:
                raise RuntimeError(f"Authorization action '{action}' must not give '{source}' a relationship")
            rules.append(PolicyRule(source=source, relationship=relationship, scope=scope))
        actions[action] = ActionPolicy(
            description=_required_text(raw_action.get("description"), f"{action}.description"),
            resource=_required_text(raw_action.get("resource"), f"{action}.resource"),
            rules=tuple(rules),
        )
    return AuthorizationPolicy(version=1, actions=actions)


class AuthorizationService:
    """Evaluate configured policy against current PostgreSQL relationship facts."""

    def __init__(self, user: CurrentUser, connection: Connection[Any], policy: AuthorizationPolicy) -> None:
        self.user = user
        self.connection = connection
        self.policy = policy
        self._access_roles: frozenset[str] | None = None
        self._access_role_flags: frozenset[str] | None = None
        self._groups_by_role: dict[str, frozenset[UUID]] | None = None
        self._exact_groups_by_role: dict[str, frozenset[UUID]] | None = None
        self._families_by_relationship: dict[str, frozenset[UUID]] | None = None
        self._main_contact_family_ids: frozenset[UUID] | None = None

    def scope(self, action: str) -> ResourceScope:
        action_policy = self.policy.actions.get(action)
        if action_policy is None:
            raise RuntimeError(f"Authorization action '{action}' is not defined")

        permitted_ids: set[UUID] = set()
        for rule in action_policy.rules:
            if rule.source == "authenticated" and rule.scope == "all":
                return ResourceScope(unrestricted=True)
            elif rule.source == "access_role":
                # Keep access-role handling as a complete branch. If scoped access
                # roles are supported later they cannot silently fall through.
                if rule.relationship not in self.access_roles:
                    continue
                if rule.scope == "all":
                    return ResourceScope(unrestricted=True)
            elif rule.source == "self" and rule.scope == "self":
                permitted_ids.add(self.user.contact_id)
            elif rule.source == "access_role_flag":
                if rule.relationship not in self.access_role_flags:
                    continue
                if rule.scope == "all":
                    return ResourceScope(unrestricted=True)
            elif rule.source == "group_role":
                if rule.scope in ("group", "group_and_family"):
                    # The caller's own assigned group only - no descendant
                    # walk, unlike group_descendants/all below. See
                    # documents/api-contract.md "Write authorization and CSRF".
                    exact_group_ids = self.exact_groups_by_role.get(rule.relationship or "", frozenset())
                    if rule.scope == "group_and_family":
                        permitted_ids.update(
                            self._group_and_family_resource_ids(action_policy.resource, exact_group_ids)
                        )
                    else:
                        permitted_ids.update(self._group_resource_ids(action_policy.resource, exact_group_ids))
                    continue
                group_ids = self.groups_by_role.get(rule.relationship or "", frozenset())
                if rule.scope == "all":
                    if group_ids:
                        return ResourceScope(unrestricted=True)
                    continue
                permitted_ids.update(self._group_resource_ids(action_policy.resource, group_ids))
            elif rule.source == "family_relationship":
                family_ids = self.families_by_relationship.get(rule.relationship or "", frozenset())
                permitted_ids.update(self._family_resource_ids(action_policy.resource, family_ids))
            elif rule.source == "main_contact_family" and rule.scope == "family":
                permitted_ids.update(self._family_resource_ids(action_policy.resource, self.main_contact_family_ids))
        return ResourceScope(unrestricted=False, ids=frozenset(permitted_ids))

    def allows(self, action: str, resource_id: UUID | None = None) -> bool:
        scope = self.scope(action)
        return scope.unrestricted if resource_id is None else scope.contains(resource_id)

    def require(self, action: str, resource_id: UUID | None = None) -> None:
        if not self.allows(action, resource_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to perform this action")

    @property
    def access_roles(self) -> frozenset[str]:
        if self._access_roles is None:
            rows = self.connection.execute(
                """
                SELECT ar.name
                FROM user_access_role_assignments assignment
                JOIN access_roles ar ON ar.id = assignment.access_role_id
                WHERE assignment.user_account_id = %s
                  AND assignment.start_date <= current_date
                  AND (assignment.end_date IS NULL OR assignment.end_date >= current_date)
                """,
                (self.user.account_id,),
            ).fetchall()
            self._access_roles = frozenset(row["name"] for row in rows)
        return self._access_roles

    @property
    def access_role_flags(self) -> frozenset[str]:
        """Flags (currently just "is_global") held by any of the user's active
        access role assignments, read off access_roles rather than by name."""
        if self._access_role_flags is None:
            rows = self.connection.execute(
                """
                SELECT bool_or(ar.is_global) AS is_global
                FROM user_access_role_assignments assignment
                JOIN access_roles ar ON ar.id = assignment.access_role_id
                WHERE assignment.user_account_id = %s
                  AND assignment.start_date <= current_date
                  AND (assignment.end_date IS NULL OR assignment.end_date >= current_date)
                """,
                (self.user.account_id,),
            ).fetchone()
            self._access_role_flags = frozenset({"is_global"}) if rows and rows["is_global"] else frozenset()
        return self._access_role_flags

    @property
    def groups_by_role(self) -> dict[str, frozenset[UUID]]:
        if self._groups_by_role is None:
            rows = self.connection.execute(
                """
                WITH RECURSIVE role_groups (role_name, group_id) AS (
                  SELECT rt.name, assignment.group_id
                  FROM contact_roles_groups assignment
                  JOIN role_types rt ON rt.id = assignment.role_type_id
                  WHERE assignment.contact_id = %s
                    AND assignment.start_date <= current_date
                    AND (assignment.end_date IS NULL OR assignment.end_date >= current_date)
                  UNION
                  SELECT role_groups.role_name, child.id
                  FROM groups child
                  JOIN role_groups ON role_groups.group_id = child.parent_id
                )
                SELECT role_name, group_id FROM role_groups
                """,
                (self.user.contact_id,),
            ).fetchall()
            mutable: dict[str, set[UUID]] = {}
            for row in rows:
                mutable.setdefault(row["role_name"], set()).add(row["group_id"])
            self._groups_by_role = {role: frozenset(ids) for role, ids in mutable.items()}
        return self._groups_by_role

    @property
    def exact_groups_by_role(self) -> dict[str, frozenset[UUID]]:
        """Groups the user directly holds each role in - no descendant walk,
        unlike groups_by_role. Backs the "group" scope (this exact group
        only), as distinct from "group_descendants"/"all"."""
        if self._exact_groups_by_role is None:
            rows = self.connection.execute(
                """
                SELECT rt.name AS role_name, assignment.group_id
                FROM contact_roles_groups assignment
                JOIN role_types rt ON rt.id = assignment.role_type_id
                WHERE assignment.contact_id = %s
                  AND assignment.start_date <= current_date
                  AND (assignment.end_date IS NULL OR assignment.end_date >= current_date)
                """,
                (self.user.contact_id,),
            ).fetchall()
            mutable: dict[str, set[UUID]] = {}
            for row in rows:
                mutable.setdefault(row["role_name"], set()).add(row["group_id"])
            self._exact_groups_by_role = {role: frozenset(ids) for role, ids in mutable.items()}
        return self._exact_groups_by_role

    @property
    def families_by_relationship(self) -> dict[str, frozenset[UUID]]:
        if self._families_by_relationship is None:
            rows = self.connection.execute(
                "SELECT initcap(relationship::text) AS relationship, family_unit_id FROM contact_family_units WHERE contact_id = %s",
                (self.user.contact_id,),
            ).fetchall()
            mutable: dict[str, set[UUID]] = {}
            for row in rows:
                mutable.setdefault(row["relationship"], set()).add(row["family_unit_id"])
            self._families_by_relationship = {relationship: frozenset(ids) for relationship, ids in mutable.items()}
        return self._families_by_relationship

    @property
    def main_contact_family_ids(self) -> frozenset[UUID]:
        """Family units where the caller is the current Main Contact.
        Backs the main_contact_family source - see
        documents/contact-data-expansion-design.md's write-access model."""
        if self._main_contact_family_ids is None:
            rows = self.connection.execute(
                """
                SELECT family_unit_id FROM contact_family_main_contacts
                WHERE contact_id = %s AND end_date IS NULL
                """,
                (self.user.contact_id,),
            ).fetchall()
            self._main_contact_family_ids = frozenset(row["family_unit_id"] for row in rows)
        return self._main_contact_family_ids

    def _group_resource_ids(self, resource: str, group_ids: frozenset[UUID]) -> set[UUID]:
        if resource == "group":
            return set(group_ids)
        if resource == "contact" and group_ids:
            rows = self.connection.execute(
                """
                SELECT DISTINCT contact_id FROM contact_roles_groups
                WHERE group_id = ANY(%s)
                  AND start_date <= current_date
                  AND (end_date IS NULL OR end_date >= current_date)
                """,
                (list(group_ids),),
            ).fetchall()
            return {row["contact_id"] for row in rows}
        return set()

    def _group_and_family_resource_ids(self, resource: str, group_ids: frozenset[UUID]) -> set[UUID]:
        """Direct group members, extended through contact_family_units to
        every other member of each group member's family unit(s) - any
        relationship, not only parent. See documents/api-contract.md "Write
        authorization and CSRF" for why this exists alongside plain "group"."""
        direct = self._group_resource_ids(resource, group_ids)
        if resource != "contact" or not direct:
            return direct
        rows = self.connection.execute(
            """
            SELECT DISTINCT other.contact_id
            FROM contact_family_units member_link
            JOIN contact_family_units other ON other.family_unit_id = member_link.family_unit_id
            WHERE member_link.contact_id = ANY(%s)
            """,
            (list(direct),),
        ).fetchall()
        return direct | {row["contact_id"] for row in rows}

    def _family_resource_ids(self, resource: str, family_ids: frozenset[UUID]) -> set[UUID]:
        if resource == "family":
            return set(family_ids)
        if resource == "contact" and family_ids:
            rows = self.connection.execute(
                "SELECT DISTINCT contact_id FROM contact_family_units WHERE family_unit_id = ANY(%s)",
                (list(family_ids),),
            ).fetchall()
            return {row["contact_id"] for row in rows}
        return set()


def get_authorization_service(
    user: CurrentUser = Depends(get_current_user),
    connection: Connection[Any] = Depends(get_connection),
) -> AuthorizationService:
    return AuthorizationService(user, connection, load_policy())
