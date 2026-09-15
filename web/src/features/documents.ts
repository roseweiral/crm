/**
 * Documentation browser frontend types and link resolution.
 *
 * Mirrors app/models/documents.py and documents/api-contract.md
 * "Documentation browser" — see web/README.md for the screen that
 * consumes these.
 */

export interface DocumentSummary {
  id: string;
  title: string;
  category: string;
  path: string;
}

export interface DocumentList {
  items: DocumentSummary[];
}

export interface DocumentDetail {
  id: string;
  title: string;
  category: string;
  path: string;
  content: string;
}

/** Resolves a possibly-relative href against a repo-relative base path. */
function resolveRelativePath(basePath: string, href: string): string {
  const resultParts = basePath.split("/").slice(0, -1);
  for (const part of href.split("/")) {
    if (part === "" || part === ".") continue;
    if (part === "..") {
      resultParts.pop();
    } else {
      resultParts.push(part);
    }
  }
  return resultParts.join("/");
}

/**
 * Resolves a markdown link's href, found inside the document at
 * `currentPath`, to another manifest document's id — or null if it isn't
 * one (an external URL, an in-page anchor, or a file outside the manifest,
 * such as documents/database/db.dbml or an image).
 */
export function resolveDocumentLink(
  currentPath: string,
  href: string,
  pathToId: Map<string, string>,
): string | null {
  if (/^[a-z][a-z0-9+.-]*:/i.test(href) || href.startsWith("//")) {
    return null;
  }
  const [hrefPath] = href.split("#");
  if (!hrefPath) {
    return null;
  }
  const resolved = hrefPath.startsWith("/") ? hrefPath.slice(1) : resolveRelativePath(currentPath, hrefPath);
  return pathToId.get(resolved) ?? null;
}
