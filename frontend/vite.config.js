import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],

  server: {
    // Vite dev proxy — forwards /api/* requests to Flask backend.
    // This completely eliminates CORS: the browser talks only to localhost:5173 (same origin),
    // and Vite makes the actual HTTP request to Flask server-side (no browser origin check).
    proxy: {
      "/api": {
        target: "http://127.0.0.1:5000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
        // Retry connection: don't fail hard if Flask is still starting
        configure: (proxy) => {
          proxy.on("error", (err) => {
            console.warn("[Vite Proxy] Backend not reachable yet:", err.code);
          });
        },
      },
    },
  },
});
