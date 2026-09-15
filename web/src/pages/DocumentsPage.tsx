import { useEffect, useMemo, useState, type ComponentPropsWithoutRef } from "react";
import { Link, useParams } from "react-router-dom";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { resolveDocumentLink, type DocumentDetail, type DocumentSummary } from "../features/documents";
import { ApiError, getDocument, getDocuments } from "../services/api";

function shiftedHeading(Tag: "h2" | "h3" | "h4" | "h5" | "h6") {
  return function Heading(props: ComponentPropsWithoutRef<"h1">) {
    return <Tag {...props} />;
  };
}

// Shifts every heading in rendered markdown down one level, so the page's
// own <h1> (the document's manifest title) remains the sole top-level
// heading instead of competing with the document's own "# ..." heading.
const HEADING_COMPONENTS: Components = {
  h1: shiftedHeading("h2"),
  h2: shiftedHeading("h3"),
  h3: shiftedHeading("h4"),
  h4: shiftedHeading("h5"),
  h5: shiftedHeading("h6"),
  h6: shiftedHeading("h6"),
};

function createLinkComponent(documentPath: string, pathToId: Map<string, string>): Components["a"] {
  return function DocumentLink({ href, children }) {
    const resolvedId = href ? resolveDocumentLink(documentPath, href, pathToId) : null;
    if (resolvedId) {
      return <Link to={`/documents/${resolvedId}`}>{children}</Link>;
    }
    return (
      <a href={href} rel="noopener noreferrer" target="_blank">
        {children}
      </a>
    );
  };
}

export function DocumentsPage() {
  const { id } = useParams<{ id?: string }>();

  const [items, setItems] = useState<DocumentSummary[] | null>(null);
  const [listError, setListError] = useState(false);

  const [openDocument, setOpenDocument] = useState<DocumentDetail | null>(null);
  const [documentLoading, setDocumentLoading] = useState(false);
  const [documentStatus, setDocumentStatus] = useState<"ok" | "not-found" | "error">("ok");

  useEffect(() => {
    const controller = new AbortController();
    getDocuments(controller.signal)
      .then((result) => setItems(result.items))
      .catch(() => {
        if (!controller.signal.aborted) setListError(true);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!id) {
      setOpenDocument(null);
      return;
    }
    const controller = new AbortController();
    setDocumentLoading(true);
    setDocumentStatus("ok");
    getDocument(id, controller.signal)
      .then((result) => setOpenDocument(result))
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setDocumentStatus(reason instanceof ApiError && reason.status === 404 ? "not-found" : "error");
      })
      .finally(() => {
        if (!controller.signal.aborted) setDocumentLoading(false);
      });
    return () => controller.abort();
  }, [id]);

  const pathToId = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of items ?? []) {
      map.set(item.path, item.id);
    }
    return map;
  }, [items]);

  const categories = useMemo(() => {
    const grouped = new Map<string, DocumentSummary[]>();
    for (const item of items ?? []) {
      const list = grouped.get(item.category) ?? [];
      list.push(item);
      grouped.set(item.category, list);
    }
    return grouped;
  }, [items]);

  return (
    <main>
      <nav className="toolbar" aria-label="Page navigation">
        <Link className="button secondary" to="/">
          Home
        </Link>
      </nav>

      <p className="eyebrow">Volunteer CRM // Documentation</p>
      <h1>{id && documentStatus === "ok" && openDocument ? openDocument.title : "Documentation"}</h1>

      <div className="documents-layout">
        <nav aria-label="Documentation index" className="documents-sidebar">
          {items === null && !listError && <p role="status">Loading documentation…</p>}
          {listError && (
            <p className="error" role="alert">
              Unable to load the documentation index.
            </p>
          )}
          {items !== null &&
            [...categories.entries()].map(([category, entries]) => (
              <div className="documents-category" key={category}>
                <h2>{category}</h2>
                <ul>
                  {entries.map((entry) => (
                    <li key={entry.id}>
                      <Link aria-current={entry.id === id ? "page" : undefined} to={`/documents/${entry.id}`}>
                        {entry.title}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
        </nav>

        <div className="documents-content">
          {!id && <p>Select a document to read it.</p>}

          {id && documentLoading && <p role="status">Loading…</p>}

          {id && !documentLoading && documentStatus === "not-found" && (
            <p className="permission-notice">This document doesn&apos;t exist.</p>
          )}

          {id && !documentLoading && documentStatus === "error" && (
            <p className="error" role="alert">
              Unable to load this document.
            </p>
          )}

          {id && !documentLoading && documentStatus === "ok" && openDocument && (
            <article>
              <ReactMarkdown
                components={{ ...HEADING_COMPONENTS, a: createLinkComponent(openDocument.path, pathToId) }}
                remarkPlugins={[remarkGfm]}
              >
                {openDocument.content}
              </ReactMarkdown>
            </article>
          )}
        </div>
      </div>
    </main>
  );
}
