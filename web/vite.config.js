import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";


export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: ["frontend"],
    host: "0.0.0.0",
  },
});
