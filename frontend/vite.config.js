import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: fileURLToPath(new URL("../web", import.meta.url)),
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8765",
      "/corpus": "http://127.0.0.1:8765",
    },
  },
});
