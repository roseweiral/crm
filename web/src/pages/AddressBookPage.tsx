import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import type { AddressBookEntry, AddressBookRole } from "../features/addressBook";
import { ApiError, getAddressBook } from "../services/api";

const PAGE_SIZE = 25;

interface GroupNode {
  name: string;
  parentId: string | null;
}

interface GroupOption {
  id: string;
  name: string;
  depth: number;
}

/**
 * Builds the org-structure filter's options from whatever group_paths the
 * address book itself has already returned, rather than a separate
 * /api/v1/groups call — that endpoint is hierarchy-scoped
 * (AuthorizationService "group:view"), while the address book is
 * deliberately org-wide, so it would silently under-populate the filter for
 * any viewer without global hierarchy scope. Options only ever grow as more
 * pages/filters are loaded; a fresh page load always includes at least the
 * unfiltered first page.
 */
function mergeGroupNodes(nodes: Map<string, GroupNode>, entries: AddressBookEntry[]): void {
  for (const entry of entries) {
    for (const role of entry.roles) {
      if (role.kind !== "group_role") continue;
      role.group_path.forEach((node, index) => {
        if (!nodes.has(node.id)) {
          nodes.set(node.id, {
            name: node.name,
            parentId: index > 0 ? role.group_path[index - 1].id : null,
          });
        }
      });
    }
  }
}

function depthOf(id: string, nodes: Map<string, GroupNode>): number {
  let depth = 0;
  let current = nodes.get(id);
  const seen = new Set<string>([id]);
  while (current?.parentId && !seen.has(current.parentId)) {
    seen.add(current.parentId);
    depth += 1;
    current = nodes.get(current.parentId);
  }
  return depth;
}

function groupOptions(nodes: Map<string, GroupNode>): GroupOption[] {
  return [...nodes.entries()]
    .map(([id, node]) => ({ id, name: node.name, depth: depthOf(id, nodes) }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

function roleLabel(role: AddressBookRole): string {
  if (role.kind === "access_role") {
    return role.access_role_name;
  }
  return `${role.role_type_name} — ${role.group_path.map((node) => node.name).join(" › ")}`;
}

export function AddressBookPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const page = Math.max(1, Number.parseInt(searchParams.get("page") ?? "1", 10) || 1);
  const groupId = searchParams.get("group");

  const [items, setItems] = useState<AddressBookEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<"ok" | "forbidden" | "error">("ok");
  const groupNodes = useRef(new Map<string, GroupNode>());
  const [, forceGroupOptionsUpdate] = useState(0);
  const hasSeededGroupOptions = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setStatus("ok");

    getAddressBook(page, PAGE_SIZE, groupId, controller.signal)
      .then((result) => {
        setItems(result.items);
        setTotal(result.total);
        mergeGroupNodes(groupNodes.current, result.items);
        forceGroupOptionsUpdate((value) => value + 1);

        // Seed the filter's options from a larger, unfiltered snapshot, once
        // we know the viewer is actually eligible to browse at all, and only
        // once — independent of whatever page/filter is currently displayed
        // (that view stays at the documented default page size). Without
        // this, a branch that only shows up past the displayed page's cutoff
        // could never be selected in the filter.
        if (!hasSeededGroupOptions.current) {
          hasSeededGroupOptions.current = true;
          getAddressBook(1, 100, null, controller.signal)
            .then((seedResult) => {
              mergeGroupNodes(groupNodes.current, seedResult.items);
              forceGroupOptionsUpdate((value) => value + 1);
            })
            .catch(() => {
              // Best-effort enrichment of the filter's options; the main
              // fetch above already surfaces real load failures.
            });
        }
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setStatus(reason instanceof ApiError && reason.status === 403 ? "forbidden" : "error");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [page, groupId]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function setPage(nextPage: number) {
    const next = new URLSearchParams(searchParams);
    next.set("page", String(nextPage));
    setSearchParams(next);
  }

  function setGroupFilter(nextGroupId: string) {
    const next = new URLSearchParams(searchParams);
    if (nextGroupId) {
      next.set("group", nextGroupId);
    } else {
      next.delete("group");
    }
    next.set("page", "1");
    setSearchParams(next);
  }

  return (
    <main>
      <nav className="toolbar" aria-label="Page navigation">
        <Link className="button secondary" to="/">
          Home
        </Link>
        <Link className="button secondary" to="/address-book/visibility">
          Manage my visibility
        </Link>
      </nav>

      <p className="eyebrow">Volunteer directory // Online</p>
      <h1>Address Book</h1>

      <div className="filter-row">
        <label htmlFor="address-book-group-filter">Filter by organisation structure</label>
        <select
          id="address-book-group-filter"
          value={groupId ?? ""}
          onChange={(event) => setGroupFilter(event.target.value)}
        >
          <option value="">Whole organisation</option>
          {groupOptions(groupNodes.current).map((option) => (
            <option key={option.id} value={option.id}>
              {"— ".repeat(option.depth)}
              {option.name}
            </option>
          ))}
        </select>
      </div>

      {loading && <p role="status">Loading the address book…</p>}

      {!loading && status === "forbidden" && (
        <p className="permission-notice">
          You need an active Group Leader, Group Helper, Area Manager, or System Administrator role to
          browse the address book.
        </p>
      )}

      {!loading && status === "error" && (
        <p className="error" role="alert">
          Unable to load the address book.
        </p>
      )}

      {!loading && status === "ok" && items.length === 0 && (
        <p>
          No one matches this filter yet.
          {groupId && (
            <>
              {" "}
              <button className="secondary" onClick={() => setGroupFilter("")} type="button">
                Clear filter
              </button>
            </>
          )}
        </p>
      )}

      {!loading && status === "ok" && items.length > 0 && (
        <>
          <ul className="results">
            {items.map((entry) => (
              <li key={entry.contact_id}>
                <div className="address-book-entry">
                  <strong>
                    {entry.first_name} {entry.last_name}
                  </strong>
                  <span className="email">{entry.email ?? "None"}</span>
                  <ul className="role-list">
                    {entry.roles.map((role, index) => (
                      <li key={index}>{roleLabel(role)}</li>
                    ))}
                  </ul>
                </div>
              </li>
            ))}
          </ul>

          <nav className="pagination" aria-label="Pagination">
            <button className="secondary" disabled={page === 1} onClick={() => setPage(page - 1)} type="button">
              Previous
            </button>
            <span>
              Page {page} of {totalPages}
            </span>
            <button
              className="secondary"
              disabled={page >= totalPages}
              onClick={() => setPage(page + 1)}
              type="button"
            >
              Next
            </button>
          </nav>
        </>
      )}
    </main>
  );
}
