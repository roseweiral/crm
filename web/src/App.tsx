import { useState } from "react";

import { resources, type ResourceDefinition } from "./features/resources";
import { HomePage } from "./pages/HomePage";
import { ResourcePage } from "./pages/ResourcePage";


export function App() {
  const [selectedResource, setSelectedResource] = useState<ResourceDefinition | null>(null);

  if (selectedResource) {
    return <ResourcePage resource={selectedResource} onHome={() => setSelectedResource(null)} />;
  }

  return <HomePage resources={resources} onSelect={setSelectedResource} />;
}
