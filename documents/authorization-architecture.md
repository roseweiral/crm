# Authorization architecture

## Status

This document records the agreed direction for authorization (AuthZ) in the
Volunteer CRM. It defines the boundary between CRM membership data and the policy
engine so that the current PostgreSQL implementation can evolve to OpenFGA without
changing every API endpoint.

The application authorization service and its first file-based policy are now
implemented. The active policy is
[`app/policies/authorization.toml`](../app/policies/authorization.toml).

The permission catalogue and write-operation matrix remain to be agreed before
write endpoints are introduced.

## Decision

PostgreSQL is the source of truth for organisational and family facts. This includes:

- contacts and user accounts;
- groups and the group hierarchy;
- a contact's role in a group, including its start and end dates; and
- family units and a contact's relationship to each family.

These are CRM business records, not authorization-engine records. OpenFGA will not
be used to create, edit, or own group membership, organisational roles, family
membership, or family relationships.

Authorization asks a different question: whether a particular user may perform an
action on a particular resource. The application exposes one authorization
interface for that question. The initial evaluator uses PostgreSQL, but the
interface and vocabulary are designed so OpenFGA can become the policy engine later.

OpenFGA is therefore a planned authorization component, not a membership database.
Introducing it may be deferred while the policy is small, but endpoints must not
embed assumptions that would prevent that migration.

## Model

The model separates three concepts:

1. **Facts** describe the organisation: for example, Alice is a Group Leader of
   Group A, Group A belongs to Area North, and Bob is a child in Family F.
2. **Policy** describes what relationships imply: for example, a Group Leader may
   read contacts in their group, and a parent may read members of their family.
3. **Decision** evaluates a user, action, and resource using the current facts and
   policy.

The guiding rule is:

> Roles grant actions; relationships determine the resources on which those actions
> may be performed.

A role name is not itself an endpoint permission. Mappings from organisational roles
or family relationships to permissions must be explicit, reviewable, and tested.

## Application-facing interface

All protected operations use a common authorization service with semantics
equivalent to:

```text
check(user, action, resource) -> allow | deny
```

Collection endpoints additionally need a way to constrain queries:

```text
scope(user, action, resource_type) -> permitted resource scope
```

`AuthorizationService.scope()` constrains collection queries and
`AuthorizationService.allows()` or `require()` makes individual decisions. Endpoint
code must not contain
its own hierarchy or family traversal rules. Authentication establishes who the user
is; authorization checks every requested action and resource.

The default is deny. The React interface may hide unavailable actions for usability,
but the API is always the enforcement boundary.

## Permission vocabulary

Permissions should describe stable business actions rather than screens or HTTP
methods. The initial catalogue to refine is:

- `contact:view` and `contact:update`;
- `family:view` and `family:update`;
- `group:view` and `group:manage`;
- `membership:manage`;
- `invitation:create`; and
- `role:assign`.

Names are singular and use `resource:action`. A new permission requires documented
resource semantics and allow/deny tests before an endpoint relies on it.

## Initial relationship rules

- Global System Administrator may perform granted administrative actions across all
  CRM resources.
- Area Manager and Group Leader permissions are scoped to their assigned group and,
  where the policy says so, its descendants.
- A parent may view their own contact and contacts connected through the same family
  unit.
- A child may view their own contact.
- A contact with no additional relationship receives only explicitly defined
  self-service permissions.
- A user may hold multiple roles and family relationships. Effective access is the
  union of currently active grants.
- An end-dated organisational or access-role assignment stops granting access at the
  end of its validity. No cleanup job is required for revocation to take effect.
- No relationship implies write access until that action is present in the agreed
  policy matrix.

Group membership and authorization scope are related but not identical. PostgreSQL
answers which groups and roles a contact belongs to. Policy answers what those facts
allow the signed-in user to do.

## PostgreSQL evaluator

The current evaluator derives permitted contacts and groups from active database
relationships. It is an interim implementation of the common authorization
interface, not a second source of membership data.

The TOML policy is loaded and validated by the application. Each action has a plain
language description, a resource kind, and one or more commented relationship rules.
Unknown actions fail rather than defaulting to an accidental grant. Policy changes
require an application restart because the validated policy is cached per process.

While PostgreSQL evaluates policy:

- shared rules belong in the authorization service, not individual routers;
- collection and detail endpoints must enforce the same policy;
- role dates and account/contact status are evaluated at request time;
- recursive group traversal has one canonical implementation; and
- tests cover both permitted access and denial across unrelated branches and
  families.

## Future OpenFGA integration

When OpenFGA is introduced, PostgreSQL remains authoritative for CRM facts. A
synchronization component projects the relationships needed for authorization into
OpenFGA tuples. For example, it may project a user-to-contact identity, active group
roles, group parentage, and family relationships.

The application will ask OpenFGA for authorization decisions through the same common
interface. It must not query OpenFGA to reconstruct CRM screens or treat tuples as
the canonical history of membership.

The integration must define:

- how database changes publish tuple additions and removals;
- how expired roles are removed or made ineffective;
- retry and reconciliation behavior after partial failure;
- the maximum acceptable delay before revocation takes effect;
- behavior when OpenFGA is unavailable; and
- how a decision can be explained and audited.

For sensitive actions, failure to obtain a reliable decision fails closed. A periodic
reconciliation process should detect and repair drift between PostgreSQL facts and
projected tuples.

## When to introduce OpenFGA

Migration should be considered when policy relationships or exceptions become hard
to express and test centrally, particularly when the CRM adds:

- delegated or record-specific access;
- user-configurable roles;
- several resource types connected through relationship chains;
- multiple organisations or tenancy boundaries;
- complex guardian or cross-family rules; or
- a need for consistent decision explanations across multiple services.

The migration should not be triggered merely to store group membership: that remains
a normal CRM data concern in PostgreSQL.

## Required policy work

Before adding write endpoints, create a policy matrix covering every action and
resource type. It must specify:

- which role or relationship grants the action;
- whether the scope is self, family, assigned group, descendants, or global;
- how multiple memberships combine;
- which resource owns the scope when records connect to several groups or families;
- the response for inaccessible resources (`403` or concealment with `404`); and
- tests for allowed, denied, expired, archived, and cross-branch cases.

Open questions about guardians, children becoming adults, conflicting memberships,
and cross-group families remain in [AnadA.md](AnadA.md).
