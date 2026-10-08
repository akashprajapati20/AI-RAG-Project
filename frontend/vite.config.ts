import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  // strictPort: the API's CORS settings allow exactly this origin (http://localhost:5173).
  server: { port: 5173, strictPort: true },
});
