import { Link } from "react-router-dom";

export function HomePage() {
  return (
    <main>
      <header className="hero-panel">
        <div className="title-bar">
          <span>CRM_HOME.EXE</span>
          <span aria-hidden="true">■ □ ×</span>
        </div>
        <p className="eyebrow">Volunteer CRM // System ready</p>
        <h1>Hello World</h1>
        <p className="welcome">Welcome to the New FAB CRM</p>
      </header>

      <section className="query-panel" aria-labelledby="address-book-heading">
        <h2 id="address-book-heading">Address Book</h2>
        <p>Browse volunteers across the whole organisation.</p>
        <Link className="button" to="/address-book">
          Address Book
        </Link>
      </section>

      <section className="query-panel" aria-labelledby="documentation-heading">
        <h2 id="documentation-heading">Documentation</h2>
        <p>Browse the project&apos;s own architecture and process documentation.</p>
        <Link className="button" to="/documents">
          Documentation
        </Link>
      </section>

      <section className="query-panel" aria-labelledby="resources-heading">
        <h2 id="resources-heading">Explore the data</h2>
        <Link className="button secondary" to="/resources">
          Open the API browser
        </Link>
      </section>
    </main>
  );
}
