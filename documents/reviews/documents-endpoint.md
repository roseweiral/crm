# Documentation browser API review

## Delivered scope

`GET /api/v1/documents` (list) and `GET /api/v1/documents/{id}` (content),
serving the repository's own markdown documentation — 13 files under
`documents/` plus 9 more `README.md` files elsewhere in the repo, 23 total —
to any signed-in contact. Contract: `documents/api-contract.md`
"Documentation browser". Executable coverage:
`tests/api/test_documents_endpoints.py` (contract) and a new smoke check in
`tests/api/test_environment.py`.

## TDD evidence

- 8 cases (contract) plus 1 (smoke) written directly from the contract,
  confirmed red for the intended reason before implementation: missing
  routes (404 from routing) and a `ModuleNotFoundError` for the
  not-yet-created `documents` module.
- Two issues surfaced while turning them green, both fixed before calling
  it done (see below) — one was the tests exercising the wrong thing, one
  was a real deployment gap.
- After fixes: full suite passes — 223 tests (3 smoke, 166 contract, 54
  regression) — both on a fresh database and repeated without a reset.

## Issues found and fixed

1. **The `api-tester` container never had access to the mounted documents.**
   The plan only added the new read-only mounts to the `app` service in
   `compose.yaml`. The HTTP-level tests still passed (they go through `app`,
   which was mounted correctly), but the new smoke check — which imports
   `documents.py` directly and reads `DOCUMENTS_ROOT` from the test
   process's own filesystem, not over HTTP — failed immediately:
   `/reference-docs/README.md` didn't exist inside `api-tester`. Fixed by
   adding the identical set of mounts (and `DOCUMENTS_ROOT`) to
   `api-tester`'s service definition too. `compose.test.yaml`'s `app`
   service already had them from the same original change.
2. **The path-traversal regression test wasn't testing what it claimed to.**
   It sent a URL-encoded `../../../../etc/passwd` as the `id` path segment.
   `GET /api/v1/documents/{document_id}` is a single-segment route; Starlette
   decodes `%2F` before matching and a single-segment pattern can't contain
   a raw `/`, so the request never reached `get_document()` at all — it hit
   Starlette's own 404 handler, not the manifest-lookup code the test meant
   to exercise. Rewritten to send a dot-heavy id with no slash
   (`....etcpasswd`), which *does* reach `get_document()` and confirms
   `get_manifest_entry()` treats it as an ordinary miss. The original
   slash-bearing case is still meaningfully blocked, just by routing, not
   application code — worth knowing, not worth a test that can't observe it.
3. **Test category placement**: the manifest-readability check was
   initially written into `test_documents_endpoints.py` under that file's
   blanket `contract` marker. It doesn't make an HTTP request at all — it's
   an environment/mount-configuration check, exactly what
   `test_environment.py`'s `smoke` category already exists for (and it
   should fail *before* the more expensive contract suite runs, not
   alongside it). Moved there.

## Prioritized follow-up improvements

1. **Mount list has to be kept in sync by hand** in three places
   (`compose.yaml`'s `app` and `api-tester` services, `compose.test.yaml`'s
   `app` service) plus the manifest in `app/documents.py` plus the index
   table in `README.md` — four places total for one new document. The smoke
   check catches a missing mount immediately, but nothing catches a
   manifest entry that was never added to `README.md`'s own table, or vice
   versa. Low cost today (23 fixed files); revisit if this list grows fast
   enough that manual sync becomes error-prone.
2. **No content-encoding safety net.** `load_document_content()` assumes
   UTF-8 and lets `read_text()` raise on anything else, matching the
   codebase's general "don't defend against scenarios that can't happen"
   stance — every manifest file is team-authored plain-text markdown, and
   the smoke check already proves every entry is a real, readable file
   before any request would hit this path. Revisit only if the manifest
   ever admits non-authored or binary content.

## Deployment and operational notes

New read-only bind mounts required on every environment that serves this
endpoint: `compose.yaml` (`app` and `api-tester` services) and
`compose.test.yaml` (`app` service, which is what the real internet-facing
test deployment also builds from — see `documents/test-deployment.md`).
Adding a new document requires four coordinated edits: a manifest entry in
`app/documents.py`, a mount line in whichever compose file(s) that
environment uses, a row in `README.md`'s documentation index (source of the
category/title convention this manifest mirrors), and — once the frontend
pass lands — nothing else, since the frontend reads the manifest through
the API rather than holding its own copy.
