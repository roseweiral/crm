import React from "react";
import ReactDOM from "react-dom/client";

import "./styles/main.css";


function App() {
  return (
    <main>
      <h1>Volunteer CRM</h1>
      <p>The local frontend is running.</p>
    </main>
  );
}


ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
