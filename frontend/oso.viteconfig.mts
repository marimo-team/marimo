// Overrides the Vite config for the OSO project
import config from "./vite.config.mjs";
import { defineConfig } from "vite";

export default defineConfig({
  ...config,
  // Add any OSO-specific config here
  build: {
    rollupOptions: {
      input: {
        "oso.js": "./src/oso.tsx",
        "wasm/controller.js": "./src/oso-extensions/wasm/controller.tsx",
        "wasm/controller-[hash].js": "./src/oso-extensions/wasm/controller.tsx",
        "index.html": "./index.html",
        "notebook.html": "./notebook.html"
      },
      output: {
        entryFileNames: (chunk) => {
          const splitName = chunk.name.split(".");
          const extension = splitName.pop();
          const name = splitName.join(".");
          if (name === "wasm/controller") {
            return "wasm/controller.js";
          }
          if (extension === "html") {
            // HTML files are not hashed
            return `${name}-[hash].js`;
          }
          return `${name}-[hash].js`;
        },
      },
    },
  },
});
