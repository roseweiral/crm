import { useState } from "react";
import { Link } from "react-router-dom";

import { resources, type ResourceDefinition } from "../features/resources";
import { ResourcePage } from "./ResourcePage";

/**
 * The original disposable generic API browser — unchanged behavior, just
 * relocated from the Home page to its own route (see web/README.md).
 */
export function ResourcesPage() {
  const [selectedResource, setSelectedResource] = useState<ResourceDefinition | null>(null);

  if (selectedResource) {
    return <ResourcePage onHome={() => setSelectedResource(null)} resource={selectedResource} />;
  }

  return (
    <main>
      <nav className="toolbar" aria-label="Page navigation">
        <Link className="button secondary" to="/">
          Home
        </Link>
      </nav>

      <p className="eyebrow">Database browser // Online</p>
      <h1>API Browser</h1>

      <section className="query-panel" aria-labelledby="queries-heading">
        <h2 id="queries-heading">Explore the data</h2>
        <div className="resource-grid">
          {resources.map((resource) => (
            <button key={resource.key} onClick={() => setSelectedResource(resource)} type="button">
              Get {resource.title}
            </button>
          ))}
        </div>
      </section>
    </main>
  );
}
