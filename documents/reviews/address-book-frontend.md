# Address book frontend review

## Delivered scope

The frontend pass of the address book increment: a homepage entry point,
`AddressBookPage` (`/address-book`, list + org-structure filter +
pagination), and `AddressBookVisibilityPage` (`/address-book/visibility`,
self-service hide/unhide). `react-router` was introduced for these routes;
the existing generic API browser moved to `/resources` with unchanged
behavior. Full screen/state documentation:
[`web/README.md`](../../web/README.md). Executable coverage:
`tests/e2e/specs/address-book.spec.ts`,
`tests/e2e/specs/address-book-visibility.spec.ts`.

A blocking infrastructure problem had to be resolved before any of this
could be tested at all — see "Same-site cookie fix" below — and one small
backend contract addition (`group_id` filtering) was needed first; that's
covered in the addendum to
[`reviews/address-book.md`](address-book.md#addendum-group_id-filter-2026-09-15),
not here.

## Same-site cookie fix

The session cookie is `SameSite=Lax` (`app/authentication.py`), a
deliberate control. That works in interactive dev only because the
frontend and API share a "site" (`localhost`, different ports). Inside
Docker, a containerized Playwright browser reaches the frontend and API on
different hostnames (`frontend` vs `app`), which browsers treat as
different sites — a `Lax` cookie is never sent cross-site on fetch/XHR, so
no test-minted session could ever reach the API at all, independent of any
test code.

Fixed by making the browser see one origin: `web/nginx.conf` gained
`/api/` and `/auth/` proxy blocks to `app:8000`, and the e2e stack
(`compose.e2e.yaml`, `.env.e2e.example`) builds the frontend's existing
`production` (nginx) target instead of the dev Vite server. This reuses two
things that already existed rather than inventing new infrastructure: the
Dockerfile's `production` stage, and `api.ts`'s relative-URL fallback
(`apiUrl` resolves to `""` when `VITE_API_URL` isn't baked in at image
build time, which the production build never receives — so its fetches
were already same-origin-shaped, just unexercised until now). Verified
directly with `curl` before any spec was written: `/health` → 200 (served
by nginx), `/api/v1/me` → 401 (proxied to `app`), `/auth/providers` → 200
(proxied). Confirmed no effect on the real Caddy-fronted test deployment:
`deployment/Caddyfile` already reverse-proxies `/api/*` and `/auth/*`
straight to `app`, ahead of ever reaching nginx, so nginx's new blocks are
simply unreached there, not double-proxied.

## TDD evidence

- 7 new specs (plus the existing signed-out spec, 8 total) written directly
  from `web/README.md`'s documented states, confirmed red against the
  unmodified app: clean "element not found" timeouts on the
  permission-denied message, the listing, the visibility link, the group
  filter, and the visibility screen — no infrastructure failures, which
  also validated the session-minting fixtures and the same-site fix before
  any screen code existed.
- After implementation: 3 of the 8 failed on first run, for real reasons
  (below), not flaky infrastructure. Fixed, then 8/8 passed on a fresh
  volume, on two immediate reruns without a reset, and again after a final
  refactor — five consecutive fully-green runs. Confirmed no leaked
  throwaway rows after the runs (`SELECT count(*) FROM contacts WHERE
  first_name = 'E2E'` → 0), so fixture teardown holds under
  `fullyParallel: true`.
- `docker compose build frontend` (`tsc --build && vite build`) passes
  cleanly.

## Issues found and fixed

1. **Org-structure filter's documented data source was wrong.**
   `web/README.md` (written in the documentation step, before any
   implementation) said the filter would be built from `GET
   /api/v1/groups`. That endpoint is hierarchy-scoped
   (`AuthorizationService` `"group:view"`), while the address book is
   deliberately org-wide — using it would have silently under-populated
   the filter for any viewer without global scope, undermining the whole
   point of the feature. Caught while implementing, before writing that
   code: fixed by deriving filter options from the `group_path` already
   present on address-book responses instead, and corrected `web/README.md`
   to match, per the project's own rule that the doc is extended before the
   code, not left to drift from what actually got built.
2. **Filter-option discovery only looked at the currently displayed page
   (25 items).** Once real data volume (seed data plus other specs running
   in parallel) pushed a test's own throwaway group past page 1, its option
   never appeared and `selectOption` timed out — a genuine bug, not a test
   artifact. Fixed with a one-time, larger (`page_size=100`) unfiltered
   background fetch that seeds the filter independent of the displayed
   page's own size, gated to fire only once and only after a confirmed
   non-`403` load (so an ineligible viewer never triggers a second, wasted
   request).
3. **Test locator ambiguity, not an app bug:** `getByText(name)` matched
   both the session toolbar ("Signed in as ...") and the results list when
   the signed-in persona was also the entry being asserted on. Fixed by
   scoping those assertions to `.results` (`page.locator(".results")`).
4. **A hidden persona's now-empty group can never become a filter
   *option* again** (nobody eligible is left in it to derive it from) —
   confirmed correct, expected behavior, not a bug. The "hiding my whole
   profile" spec was adjusted to navigate directly to the filtered URL
   (`/address-book?group=<id>`) rather than driving the `<select>`, which
   is exactly the shareable-link use `AddressBookPage` is designed to
   support, and more precisely tests what that spec is actually for (the
   hide took effect) rather than re-testing filter-option discovery, which
   the other specs already cover.

## Prioritized follow-up improvements

1. **Stale filter selection display.** Visiting a `group_id`-filtered URL
   for a group not yet in the derived option set (the scenario spec #4
   above exercises deliberately) filters correctly but the `<select>`
   itself falls back to showing "Whole organisation" as selected. Cosmetic
   only — the underlying request and results are correct — but worth a
   "filtered" indicator or dynamically injecting the missing option.
2. **Reverse-proxy logic now exists in two places** (`deployment/Caddyfile`
   for the real test deployment, `web/nginx.conf` for local/CI e2e).
   Confirmed non-conflicting today (Caddy fully resolves `/api`/`/auth`
   before nginx ever sees them), but they could drift independently — for
   example, a header added to one and not the other. Revisit if a third
   consumer appears or if header parity starts to matter.
3. **Group filter is a flat, alphabetically-sorted `<select>`**, not a true
   tree ordering. Matches the "simplest widget that satisfies filter by org
   structure" scope decision from planning; upgradeable to a proper
   tree/breadcrumb control later without changing the underlying data.
4. **No detail/click-through view for an address-book entry** — deliberate:
   the list already shows full entries (name, email, all visible roles with
   group breadcrumbs) inline, matching the API contract's own note that
   this, unlike family units, doesn't defer detail to a second request.
   Revisit only if a real need for a dedicated per-person view emerges.

## Deployment and operational notes

No backend deployment changes beyond the already-covered `group_id` filter
addendum. The e2e stack (`compose.e2e.yaml` + `.env.e2e.example`) is
local/CI tooling only — it doesn't touch `compose.yaml`'s interactive dev
service or `compose.test.yaml`'s real test deployment. Running it:

```shell
docker compose --env-file .env.e2e.example -f compose.yaml -f compose.e2e.yaml \
  -p crm-e2e --profile test run --rm --build e2e-tester
docker compose --env-file .env.e2e.example -f compose.yaml -f compose.e2e.yaml \
  -p crm-e2e --profile test down -v
```
