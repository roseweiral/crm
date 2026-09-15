# Documentation browser frontend review

## Delivered scope

The frontend pass of the documentation browser: `DocumentsPage` serving
both `/documents` (sidebar only) and `/documents/:id` (sidebar + rendered
document), reachable from a new Documentation panel on the homepage.
Full screen/state documentation: [`web/README.md`](../../web/README.md)
"Documentation (`/documents`, `/documents/:id`)". Executable coverage:
`tests/e2e/specs/documents.spec.ts`. Backend: reviewed separately in
[`reviews/documents-endpoint.md`](documents-endpoint.md).

## TDD evidence

- 5 specs written directly from `web/README.md`, confirmed red against the
  unmodified app before any component existed: 4 clean "element not found"
  failures, 1 pass (the sign-in gate already covers any path, including
  the not-yet-built `/documents` routes).
- Two of the five red assertions were wrong on first pass, not the app:
  one asserted a phrase ("11-step cycle") that only ever existed in
  `README.md`'s description of `way-of-working.md`, never in the document
  itself — fixed to assert on `way-of-working.md`'s own text ("Agree the
  deliverable"). The other hit a real strict-mode ambiguity once real
  content rendered (see below).
- After implementation: 13/13 e2e tests pass (the 5 new plus the existing
  8), on a fresh volume and on two immediate reruns without a reset.
  `docker compose build frontend` (`tsc --build && vite build`) passes
  cleanly throughout.

## Issues found and fixed

1. **Two `<h1>` elements on the same page.** The page always rendered
   `<h1>Documentation</h1>`, and — when a document was open — the content
   pane *also* rendered `<h1>{document.title}</h1>`, defeating the whole
   point of the heading-shift logic (which only prevented the document's
   own embedded `# heading` from competing with a *second* `<h1>`, while
   missing that the page chrome already had one). Fixed to match the
   pattern `ResourcePage` already established: one dynamic `<h1>` that
   shows "Documentation" or the open document's title depending on state,
   not two separate headings. The now-unused `.documents-content h1` CSS
   rule was removed with it.
2. **`document` as a state variable name shadowed the global `window.document`**
   throughout the component. Not a functional bug today — nothing in this
   component needs the real DOM `document` — but a real footgun for
   whoever edits this file next (e.g. a future `document.title = ...` for
   the browser tab would silently do nothing, since `document` would still
   resolve to the local `DocumentDetail | null`). Renamed to `openDocument`.
3. **External link hardening**: `target="_blank"` links used
   `rel="noreferrer"` only. Added `noopener` alongside it — modern browsers
   treat `noreferrer` as implying `noopener`, but pairing them explicitly is
   the established, unambiguous practice for this exact pattern.
4. **Test locator ambiguity, not an app bug**: once real content rendered,
   `getByText("Agree the deliverable")` matched both a numbered list item
   in `way-of-working.md`'s "Purpose" section and a section heading further
   down the same document ("## 1. Agree the deliverable"). Fixed with
   `.first()`, matching the same resolution used for the address book
   specs' earlier session-toolbar/results-list collision.

## Prioritized follow-up improvements

1. **Mild visual redundancy, not a defect**: the page's own `<h1>` (the
   manifest title, e.g. "Way of working") sits directly above the
   document's own first heading once shifted to `<h2>` (e.g. "Way of
   working: feature increments") — two similar-looking headings back to
   back for documents whose own first heading closely echoes their
   manifest title. Stripping a document's own leading heading before
   rendering would remove the duplication but adds real parsing complexity
   for a purely cosmetic gain; not worth it unless it reads as genuinely
   confusing in practice.
2. **Cross-link resolution has a sub-second race on direct navigation.**
   Visiting `/documents/:id` directly fires the list and detail fetches
   together; if the detail response resolves first, links render as
   external-style anchors until the list response fills `pathToId`, then
   self-correct on the next render. Self-healing and not observed to cause
   any incorrect *persistent* state (the direct-navigation e2e spec
   exercises exactly this path and passes reliably), but worth knowing —
   same class of accepted behavior as `AddressBookPage`'s progressively
   filled filter options.
3. **Sidebar category headings (`<h2>`) and shifted document headings
   (`<h1>`→`<h2>`) share a heading level** despite being semantically
   different (navigation vs. content) — differentiated for screen-reader
   users by landmark region (`<nav>` vs. the content pane) rather than
   heading level. Fine as-is; revisit only if it proves confusing in
   practice.

## Deployment and operational notes

No new deployment surface beyond the backend's mounts (already covered in
`reviews/documents-endpoint.md`). Two new frontend dependencies
(`react-markdown`, `remark-gfm`) — a local dev environment with an
already-running `frontend` container needs `npm install` re-run inside it
(and a restart, for Vite to fully clear its dependency cache) after pulling
this change, the same as when `react-router-dom` was added for the address
book frontend increment.
