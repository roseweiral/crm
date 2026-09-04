export type ApiRecord = Record<string, unknown> & { id: string };

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

const apiUrl = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${apiUrl}${path}`, { signal, credentials: "include" });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
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
