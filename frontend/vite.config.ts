import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// /api and /uploads are proxied to the FastAPI backend in development.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/uploads": "http://localhost:8000",
    },
  },
});
