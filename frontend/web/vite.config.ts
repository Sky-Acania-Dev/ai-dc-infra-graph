import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    proxy: {
      "/auth": "http://127.0.0.1:8000",
      "/change-orders": "http://127.0.0.1:8000",
      "/database": "http://127.0.0.1:8000",
      "/entity-groups": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      "/label-extraction": "http://127.0.0.1:8000",
      "/projects": "http://127.0.0.1:8000",
      "/tasks": "http://127.0.0.1:8000",
      "/topology": "http://127.0.0.1:8000",
    },
  },
});
