import { useEffect, useState } from "react";

import { RecordDetails } from "../components/RecordDetails";
import type { ResourceDefinition } from "../features/resources";
import { getCollection, getDetail, type ApiRecord, type Page } from "../services/api";

const PAGE_SIZE = 25;

interface ResourcePageProps {
  resource: ResourceDefinition;
  onHome: () => void;
}

export function ResourcePage({ resource, onHome }: ResourcePageProps) {
  const [pageNumber, setPageNumber] = useState(1);
  const [collection, setCollection] = useState<Page<ApiRecord> | null>(null);
  const [selected, setSelected] = useState<ApiRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setSelected(null);

    getCollection(resource.path, pageNumber, PAGE_SIZE, controller.signal)
      .then(setCollection)
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "Unable to load records");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [pageNumber, resource]);

  async function openDetail(id: string) {
    setLoading(true);
    setError(null);
    try {
      setSelected(await getDetail(resource.path, id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load the record");
    } finally {
      setLoading(false);
    }
  }

  const totalPages = collection ? Math.max(1, Math.ceil(collection.total / collection.page_size)) : 1;

  return (
    <main>
      <nav className="toolbar" aria-label="Page navigation">
        <button className="secondary" onClick={onHome} type="button">Home</button>
        {selected && (
          <button className="secondary" onClick={() => setSelected(null)} type="button">
            Back to {resource.title}
          </button>
        )}
      </nav>

      <p className="eyebrow">Database browser // Online</p>
      <h1>{selected ? `${resource.title} Detail` : resource.title}</h1>

      {loading && <p role="status">Loading…</p>}
      {error && <p className="error" role="alert">{error}</p>}

      {!loading && !error && selected && <RecordDetails value={selected} />}

      {!loading && !error && !selected && collection && (
        <>
          <p>{collection.total} records</p>
          <ul className="results">
            {collection.items.map((item) => (
              <li key={item.id}>
                <button onClick={() => void openDetail(item.id)} type="button">
                  <strong>{resource.describe(item)}</strong>
                  <span>{item.id}</span>
                </button>
              </li>
            ))}
          </ul>

          <nav className="pagination" aria-label="Pagination">
            <button
              className="secondary"
              disabled={pageNumber === 1}
              onClick={() => setPageNumber((current) => current - 1)}
              type="button"
            >
              Previous
            </button>
            <span>Page {collection.page} of {totalPages}</span>
            <button
              className="secondary"
              disabled={pageNumber >= totalPages}
              onClick={() => setPageNumber((current) => current + 1)}
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
