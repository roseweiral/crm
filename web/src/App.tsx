import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AddressBookPage } from "./pages/AddressBookPage";
import { AddressBookVisibilityPage } from "./pages/AddressBookVisibilityPage";
import { HomePage } from "./pages/HomePage";
import { ResourcesPage } from "./pages/ResourcesPage";
import { authenticationUrl, getMe, signOut, type CurrentUser } from "./services/api";


export function App() {
  const [user, setUser] = useState<CurrentUser | null | undefined>(undefined);
  const [signingOut, setSigningOut] = useState(false);
  const [signOutError, setSignOutError] = useState<string | null>(null);

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
    setSignOutError(null);
    try {
      await signOut();
      setUser(null);
      window.history.replaceState({}, "", window.location.pathname);
    } catch {
      setSignOutError("We could not sign you out. Please try again.");
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
        {signOutError && <p className="session-error" role="alert">{signOutError}</p>}
      </div>
      <button className="secondary" disabled={signingOut} onClick={() => void switchUser()} type="button">
        {signingOut ? "Signing out…" : "Switch user"}
      </button>
    </nav>
  );

  return (
    <BrowserRouter>
      {userControls}
      <Routes>
        <Route element={<HomePage />} path="/" />
        <Route element={<AddressBookPage />} path="/address-book" />
        <Route element={<AddressBookVisibilityPage />} path="/address-book/visibility" />
        <Route element={<ResourcesPage />} path="/resources" />
        <Route element={<Navigate replace to="/" />} path="*" />
      </Routes>
    </BrowserRouter>
  );
}
