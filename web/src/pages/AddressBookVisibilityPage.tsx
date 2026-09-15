import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import type { DirectoryVisibility, DirectoryVisibilityPatch, VisibilityRole } from "../features/addressBook";
import { ApiError, getDirectoryVisibility, updateDirectoryVisibility } from "../services/api";

function roleLabel(role: VisibilityRole): string {
  return role.kind === "access_role" ? role.access_role_name : `${role.role_type_name} — ${role.group_name}`;
}

export function AddressBookVisibilityPage() {
  const [visibility, setVisibility] = useState<DirectoryVisibility | null>(null);
  const [etag, setEtag] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [hideProfile, setHideProfile] = useState(false);
  const [hiddenRoleIds, setHiddenRoleIds] = useState<Set<string>>(new Set());

  function applyLoaded(data: DirectoryVisibility, nextEtag: string) {
    setVisibility(data);
    setEtag(nextEtag);
    setHideProfile(data.hidden_from_directory);
    setHiddenRoleIds(new Set(data.roles.filter((role) => role.hidden_from_directory).map((role) => role.id)));
  }

  function load(signal?: AbortSignal) {
    setLoading(true);
    setError(null);
    getDirectoryVisibility(signal)
      .then(({ data, etag: nextEtag }) => applyLoaded(data, nextEtag))
      .catch((reason: unknown) => {
        if (signal?.aborted) return;
        setError(reason instanceof Error ? reason.message : "Unable to load your visibility settings");
      })
      .finally(() => {
        if (!signal?.aborted) setLoading(false);
      });
  }

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, []);

  function toggleRole(roleId: string, hidden: boolean) {
    setHiddenRoleIds((current) => {
      const next = new Set(current);
      if (hidden) {
        next.add(roleId);
      } else {
        next.delete(roleId);
      }
      return next;
    });
  }

  async function save() {
    if (!visibility) return;

    const payload: DirectoryVisibilityPatch = {};
    if (hideProfile !== visibility.hidden_from_directory) {
      payload.hidden_from_directory = hideProfile;
    }
    const changedRoles = visibility.roles
      .filter((role) => hiddenRoleIds.has(role.id) !== role.hidden_from_directory)
      .map((role) => ({ id: role.id, hidden_from_directory: hiddenRoleIds.has(role.id) }));
    if (changedRoles.length > 0) {
      payload.roles = changedRoles;
    }
    if (Object.keys(payload).length === 0) {
      setConfirmation("No changes to save.");
      return;
    }

    setSaving(true);
    setError(null);
    setConfirmation(null);
    try {
      const { data, etag: nextEtag } = await updateDirectoryVisibility(payload, etag);
      applyLoaded(data, nextEtag);
      setConfirmation("Your visibility settings have been saved.");
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 412) {
        load();
        setError("This changed elsewhere — refreshed, please retry.");
      } else {
        setError(reason instanceof Error ? reason.message : "Unable to save your visibility settings");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <main>
      <nav className="toolbar" aria-label="Page navigation">
        <Link className="button secondary" to="/address-book">
          Back to Address Book
        </Link>
      </nav>

      <p className="eyebrow">Volunteer directory // Preferences</p>
      <h1>My Directory Visibility</h1>

      {loading && <p role="status">Loading your visibility settings…</p>}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {!loading && visibility && (
        <>
          {visibility.roles.length === 0 && (
            <p>
              You don&apos;t currently hold a role that appears in the address book. These settings will
              apply if you do.
            </p>
          )}

          <label className="visibility-toggle">
            <input
              checked={hideProfile}
              onChange={(event) => setHideProfile(event.target.checked)}
              type="checkbox"
            />
            Hide my profile from the address book entirely
          </label>

          {visibility.roles.length > 0 && (
            <ul className="visibility-role-list">
              {visibility.roles.map((role) => (
                <li key={role.id}>
                  <label className="visibility-toggle">
                    <input
                      checked={hiddenRoleIds.has(role.id)}
                      onChange={(event) => toggleRole(role.id, event.target.checked)}
                      type="checkbox"
                    />
                    Hide {roleLabel(role)}
                  </label>
                </li>
              ))}
            </ul>
          )}

          {confirmation && <p role="status">{confirmation}</p>}

          <button disabled={saving} onClick={() => void save()} type="button">
            {saving ? "Saving…" : "Save changes"}
          </button>
        </>
      )}
    </main>
  );
}
