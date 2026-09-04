import { useEffect, useState } from "react";

import { resources, type ResourceDefinition } from "./features/resources";
import { HomePage } from "./pages/HomePage";
import { ResourcePage } from "./pages/ResourcePage";
import { authenticationUrl, getMe, signOut, type CurrentUser } from "./services/api";


export function App() {
  const [selectedResource, setSelectedResource] = useState<ResourceDefinition | null>(null);
  const [user, setUser] = useState<CurrentUser | null | undefined>(undefined);
  const [signingOut, setSigningOut] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getMe(controller.signal).then(setUser).catch(() => setUser(null));
    return () => controller.abort();
  }, []);

  if (user === undefined) {
    return <main><p role="status">Checking your session…</p></main>;
  }

  if (user === null) {
    const invitation = new URLSearchParams(window.location.search).get("invitation");
    return (
      <main>
        <h1>Volunteer CRM</h1>
        <p>You need an invitation and an approved identity to continue.</p>
        <p><a href={authenticationUrl("google", invitation)}>Continue with Google</a></p>
        <p><a href={authenticationUrl("microsoft", invitation)}>Continue with Microsoft</a></p>
      </main>
    );
  }

  async function switchUser() {
    setSigningOut(true);
    try {
      await signOut();
      setSelectedResource(null);
      setUser(null);
      window.history.replaceState({}, "", window.location.pathname);
    } finally {
      setSigningOut(false);
    }
  }

  const userControls = (
    <nav className="session-toolbar" aria-label="User session">
      <div>
        <span>Signed in as {user.first_name} {user.last_name}</span>
        <ul className="session-roles" aria-label="Your roles">
          {user.roles.map(({ role, group }) => (
            <li key={`${role}:${group ?? ""}`}>{group ? `${role} — ${group}` : role}</li>
          ))}
        </ul>
      </div>
      <button className="secondary" disabled={signingOut} onClick={() => void switchUser()} type="button">
        {signingOut ? "Signing out…" : "Switch user"}
      </button>
    </nav>
  );

  if (selectedResource) {
    return <>{userControls}<ResourcePage resource={selectedResource} onHome={() => setSelectedResource(null)} /></>;
  }

  return <>{userControls}<HomePage resources={resources} onSelect={setSelectedResource} /></>;
}
