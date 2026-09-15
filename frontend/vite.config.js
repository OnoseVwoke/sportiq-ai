import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 3000,
  },
  preview: {
    host: "0.0.0.0",
    port: 3000,
    // Vite's preview server blocks unrecognized Host headers by
    // default. Since this only runs behind nginx/security groups
    // we control, allow all hosts rather than maintaining a list.
    allowedHosts: true,
  },
});