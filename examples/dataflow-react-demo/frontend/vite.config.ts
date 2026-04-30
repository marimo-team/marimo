import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  // ``src/dataflow.tsx`` is a symlink into ``marimo/_dataflow/clients/...``
  // so we (and the user) only ever maintain one copy. The symlink target
  // lives outside the demo's project root, so we (a) opt the React plugin
  // into transforming files outside ``src/`` and (b) explicitly allow
  // serving them from the dev server.
  plugins: [react({ include: /\.tsx?$/ })],
  server: {
    port: 5173,
    fs: {
      allow: [path.resolve(__dirname, "../../..")],
    },
    proxy: {
      "/api": {
        target: "http://localhost:2718",
        changeOrigin: true,
      },
    },
  },
});
