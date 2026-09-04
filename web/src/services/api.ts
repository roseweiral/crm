export type ApiRecord = Record<string, unknown> & { id: string };

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

const apiUrl = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${apiUrl}${path}`, { signal });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
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
