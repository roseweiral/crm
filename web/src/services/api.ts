import type { AddressBookEntry, DirectoryVisibility, DirectoryVisibilityPatch } from "../features/addressBook";
import type { DocumentDetail, DocumentList } from "../features/documents";

export type ApiRecord = Record<string, unknown> & { id: string };

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

/** Carries the HTTP status so callers can branch on it (403, 412, ...). */
export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const apiUrl = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";

async function errorFromResponse(response: Response): Promise<ApiError> {
  const body = (await response.json().catch(() => null)) as { detail?: string } | null;
  return new ApiError(response.status, body?.detail ?? `Request failed with status ${response.status}`);
}

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${apiUrl}${path}`, { signal, credentials: "include" });

  if (!response.ok) {
    throw await errorFromResponse(response);
  }

  return response.json() as Promise<T>;
}

/** GET that also returns the strong ETag needed for a later PATCH's If-Match. */
async function requestWithETag<T>(path: string, signal?: AbortSignal): Promise<{ data: T; etag: string }> {
  const response = await fetch(`${apiUrl}${path}`, { signal, credentials: "include" });

  if (!response.ok) {
    throw await errorFromResponse(response);
  }

  return { data: (await response.json()) as T, etag: response.headers.get("etag") ?? "" };
}

/** PATCH with the shared write headers every resource write requires (see write_security.py). */
async function patchJson<T>(
  path: string,
  body: unknown,
  ifMatch: string,
  signal?: AbortSignal,
): Promise<{ data: T; etag: string }> {
  const response = await fetch(`${apiUrl}${path}`, {
    method: "PATCH",
    credentials: "include",
    signal,
    headers: {
      "Content-Type": "application/json",
      "X-CRM-CSRF": "1",
      "If-Match": ifMatch,
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw await errorFromResponse(response);
  }

  return { data: (await response.json()) as T, etag: response.headers.get("etag") ?? "" };
}

export interface CurrentUser {
  account_id: string;
  contact_id: string;
  first_name: string;
  last_name: string;
  email: string | null;
  roles: Array<{ role: string; group: string | null }>;
}

export function getMe(signal?: AbortSignal): Promise<CurrentUser> {
  return request<CurrentUser>("/api/v1/me", signal);
}

export async function signOut(): Promise<void> {
  const response = await fetch(`${apiUrl}/auth/sign-out`, {
    method: "POST",
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(`Sign out failed with status ${response.status}`);
  }
}

export function authenticationUrl(
  provider: "google" | "microsoft",
  invitation?: string | null,
): string {
  const query = invitation ? `?${new URLSearchParams({ invitation })}` : "";
  return `${apiUrl}/auth/login/${provider}${query}`;
}

export function getCollection(
  path: string,
  page: number,
  pageSize: number,
  signal?: AbortSignal,
): Promise<Page<ApiRecord>> {
  const query = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  return request<Page<ApiRecord>>(`${path}?${query}`, signal);
}

export function getDetail(
  path: string,
  id: string,
  signal?: AbortSignal,
): Promise<ApiRecord> {
  return request<ApiRecord>(`${path}/${id}`, signal);
}

export function getAddressBook(
  page: number,
  pageSize: number,
  groupId: string | null,
  signal?: AbortSignal,
): Promise<Page<AddressBookEntry>> {
  const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (groupId) {
    query.set("group_id", groupId);
  }
  return request<Page<AddressBookEntry>>(`/api/v1/address-book?${query}`, signal);
}

export function getDirectoryVisibility(
  signal?: AbortSignal,
): Promise<{ data: DirectoryVisibility; etag: string }> {
  return requestWithETag<DirectoryVisibility>("/api/v1/address-book/visibility", signal);
}

export function updateDirectoryVisibility(
  patch: DirectoryVisibilityPatch,
  ifMatch: string,
  signal?: AbortSignal,
): Promise<{ data: DirectoryVisibility; etag: string }> {
  return patchJson<DirectoryVisibility>("/api/v1/address-book/visibility", patch, ifMatch, signal);
}

export function getDocuments(signal?: AbortSignal): Promise<DocumentList> {
  return request<DocumentList>("/api/v1/documents", signal);
}

export function getDocument(id: string, signal?: AbortSignal): Promise<DocumentDetail> {
  return request<DocumentDetail>(`/api/v1/documents/${encodeURIComponent(id)}`, signal);
}
