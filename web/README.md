# Web

This directory contains the React and TypeScript web application for the CRM.
Vite provides the local development server inside the `frontend` Docker Compose
service.

Most of this interface is still a disposable data browser built to exercise the
read-only API while the product design was still being formed — retro visual
treatment (monospace type, terminal colours, hard borders, offset shadows),
generic list/detail views, no router. It's expected to be replaced rather than
treated as the final CRM design.

The Address Book (below) is the first real, purpose-built feature on top of
that scaffold, and the first screen with a genuine URL — `react-router` is
introduced for it. The generic browser keeps working exactly as it always has,
just reachable at its own route instead of being the app's only view.

This section is the UI's contract: it documents every route, the states each
screen can be in, and which API calls populate them, precisely enough to write
`tests/e2e` specs directly from it before any component exists — see
[`way-of-working.md`](../documents/way-of-working.md) step 6. Do not build
screen behavior this document doesn't describe yet.

## Routes

| Path | Screen | Requires session |
| --- | --- | --- |
| `/` | Home | No (shows sign-in when signed out) |
| `/address-book` | Address Book | Yes |
| `/address-book/visibility` | My directory visibility | Yes |
| `/resources` | Generic API browser (unchanged) | Yes |

Every route sits behind the existing app-level session gate: `App.tsx`
already blocks on `GET /api/v1/me` before rendering any route, showing the
Google/Microsoft sign-in screen when signed out and a loading state
(`<p role="status">Checking your session…</p>`) while that call is in
flight. No route adds its own auth guard on top of that.

## Home (`/`)

Unchanged when signed out (Google/Microsoft "Continue with" links) and
unchanged hero panel when signed in ("Hello World" / "Welcome to the New
CRM"). Two changes to the signed-in view:

- A new, prominent **Address Book** panel below the hero: one line of copy
  ("Browse volunteers across the whole organisation.") and a link/button
  labelled `Address Book` to `/address-book`. Shown unconditionally to every
  signed-in user — no client-side eligibility check. `AddressBookPage`
  itself handles an ineligible viewer's `403`; duplicating that rule here
  would be exactly the drift `way-of-working.md` step 8 warns against.
- The existing "Explore the data" resource grid is replaced on this page by
  a single secondary link labelled `Open the API browser` to `/resources`.
  Nothing about the grid or the resource viewer behind it changes — it only
  moves behind that link instead of being inline on Home.

## Address Book (`/address-book`)

Reads `page` and `group` from the URL's query string
(`/address-book?page=2&group=<uuid>`), so the current view is a shareable
link.

**Data**: `GET /api/v1/address-book?page=&page_size=25&group_id=` on mount
and whenever `page` or the filter changes. The org-structure filter's
options are *not* fetched separately from `GET /api/v1/groups` — that
endpoint is hierarchy-scoped (`AuthorizationService` `"group:view"`), while
the address book is deliberately org-wide, so it would silently
under-populate the filter for any viewer without global hierarchy scope.
Instead, options accumulate from the `group_path` on every address-book
response seen so far (starting with the unfiltered first page on load), so
the filter only ever offers branches the viewer can already see confirmed to
have an eligible member in them.

**States**:

| State | Trigger | UI |
| --- | --- | --- |
| Loading | request in flight | `<p role="status">Loading the address book…</p>` |
| Permission denied | `403` from the address-book call | A distinct, non-alarming panel (not the red `.error` box — this is an expected outcome for most signed-in users, not a fault): "You need an active Group Leader, Group Helper, Area Manager, or System Administrator role to browse the address book." |
| Error | any other failed request | Existing `.error`/`role="alert"` pattern: "Unable to load the address book." |
| Empty | `200` with `items: []` | "No one matches this filter yet." plus a way to clear the filter, shown only when a filter is active |
| Loaded | `200` with entries | The list below |

**Loaded list**: entries in the order the API returns them (surname A–Z is
the API's default — no client-side sort). Each entry shows first + last
name, email (or the existing `RecordDetails` convention of "None" for
null), and its roles: a `group_role` renders as `{role_type_name} —
{group_path joined by " › "}`; an `access_role` renders as
`{access_role_name}`.

**Org-structure filter**: a `<select>` built from `GET /api/v1/groups`,
options indented by depth (computed from `parent_id`), with a first option
`Whole organisation` that clears the filter. Changing the selection updates
the `group` URL parameter, resets `page` to 1, and refetches.

**Pagination**: same Previous/Next pattern as the existing `ResourcePage`
(`Page {page} of {totalPages}`, buttons disabled at the bounds).

**Navigation**: a `Manage my visibility` link to `/address-book/visibility`,
and a `Home` link to `/`.

## My directory visibility (`/address-book/visibility`)

Self-service settings for the address book — available to every signed-in
contact, whether or not they're currently eligible to appear in it.

**Data**: `GET /api/v1/address-book/visibility` on mount, keeping the
response `ETag` header in state for the next save.

**States**:

| State | Trigger | UI |
| --- | --- | --- |
| Loading | request in flight | `<p role="status">Loading your visibility settings…</p>` |
| Error | failed GET, or a non-412 failed PATCH | Existing `.error`/`role="alert"` pattern |
| No eligible roles yet | `200` with `roles: []` | "You don't currently hold a role that appears in the address book. These settings will apply if you do." — the whole-profile toggle is still shown and usable |
| Stale save | `412` from PATCH | Refetch automatically, replace the held ETag, and show: "This changed elsewhere — refreshed, please retry." Do not lose the user's in-progress toggle choices when this happens. |
| Loaded | `200` | The form below |

**Form**: one toggle, `Hide my profile from the address book entirely`,
bound to `hidden_from_directory`; one toggle per role currently in `roles`,
labelled the same way as the Address Book list renders that role kind, each
bound to that role's own `hidden_from_directory`. A single `Save changes`
button sends one `PATCH /api/v1/address-book/visibility` with whichever
fields changed (`hidden_from_directory` and/or `roles`), the held `If-Match`
ETag, and the standard write headers (`X-CRM-CSRF: 1`, `Content-Type:
application/json`, browser-supplied `Origin`). On success, replace the held
ETag with the response's and show a brief confirmation.

**Navigation**: a `Back to Address Book` link to `/address-book`.

## Build, test, and run

Build and type-check the frontend through its Docker image:

```shell
docker compose build frontend
```

Run the browser tests from the repository root:

```shell
docker compose run --rm --build e2e-tester
```

The run persists an HTML report. Start its viewer with
`docker compose --profile test up -d e2e-report`, then open
`http://localhost:9323`.

Address Book and visibility specs are the project's first *authenticated*
e2e coverage. They mint a real, short-lived session directly in the test
database and install it as the browser context's cookie before navigating
(`tests/e2e/specs/support/fixtures.ts`) — the same technique
`documents/authentication-operations.md` describes for end-to-end tests
generally, no test-only login endpoint or bypass. Each spec creates its own
throwaway contacts/groups/roles and cleans them up in teardown; nothing
touches seed or demo data.

Running these specs also needs the frontend and API to share one browser
origin, so the `SameSite=Lax` session cookie actually reaches the API
(`web/nginx.conf` proxies `/api` and `/auth`; see
[`reviews/address-book-frontend.md`](../documents/reviews/address-book-frontend.md)
for why). This only works with the frontend's `production` build, not the
interactive dev server, so authenticated e2e runs use a separate, isolated
Compose project rather than `docker compose run --rm --build e2e-tester`
directly:

```shell
docker compose --env-file .env.e2e.example -f compose.yaml -f compose.e2e.yaml \
  -p crm-e2e --profile test run --rm --build e2e-tester
docker compose --env-file .env.e2e.example -f compose.yaml -f compose.e2e.yaml \
  -p crm-e2e --profile test down -v
```

See [`app/routers/README.md`](../app/routers/README.md) for the HTTP API
that this frontend consumes, and
[`documents/api-contract.md`](../documents/api-contract.md) for the address
book's full behavioral contract.
