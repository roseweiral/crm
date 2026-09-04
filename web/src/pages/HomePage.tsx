import type { ResourceDefinition } from "../features/resources";

interface HomePageProps {
  resources: ResourceDefinition[];
  onSelect: (resource: ResourceDefinition) => void;
}

export function HomePage({ resources, onSelect }: HomePageProps) {
  return (
    <main>
      <header className="hero-panel">
        <div className="title-bar">
          <span>CRM_HOME.EXE</span>
          <span aria-hidden="true">■ □ ×</span>
        </div>
        <p className="eyebrow">Volunteer CRM // System ready</p>
        <h1>Hello World</h1>
        <p className="welcome">Welcome to the New CRM</p>
      </header>

      <section className="query-panel" aria-labelledby="queries-heading">
        <h2 id="queries-heading">Explore the data</h2>
        <div className="resource-grid">
          {resources.map((resource) => (
            <button key={resource.key} onClick={() => onSelect(resource)} type="button">
              Get {resource.title}
            </button>
          ))}
        </div>
      </section>
    </main>
  );
}
