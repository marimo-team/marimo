// Overrides the Vite config for the OSO project
import config from "./vite.config.mjs";
import { defineConfig } from "vite";

export default defineConfig({
  ...config,
  // Add any OSO-specific config here
  build: {
    rollupOptions: {
        input: {
            "main": "./src/main.tsx", 
            "oso": "./src/oso.tsx",
            "wasmController": "./src/oso-extensions/wasm/controller.tsx",
            "notebook.html": "./notebook.html",
        }
    }
  }
});
