import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const apiTarget=process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    proxy: {
      "/auth": apiTarget,
      "/change-orders": apiTarget,
      "/database": apiTarget,
      "/entity-groups": apiTarget,
      "/health": apiTarget,
      "/label-extraction": apiTarget,
      "/projects": apiTarget,
      "/routing": process.env.ROUTING_API_TARGET ?? apiTarget,
      "/tasks": apiTarget,
      "/topology": apiTarget,
    },
  },
});
