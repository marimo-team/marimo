// Overrides the Vite config for the OSO project
import config from "./vite.config.mjs";
import { defineConfig } from "vite";
import * as path from "node:path";

export default defineConfig({
  ...config,
  // Add any OSO-specific config here
  build: {
    rollupOptions: {
      input: {
        "oso.js": path.resolve(__dirname, "./src/oso.tsx"),
        "wasm/controller.js": path.resolve(__dirname, "./src/oso-extensions/wasm/controller.tsx"),
        "index": path.resolve(__dirname, "./index.html"),
        "notebook": path.resolve(__dirname, "./notebook.html")
      },
      output: {
        entryFileNames: (chunk) => {
          const splitName = chunk.name.split(".");
          const name = splitName.join(".");
          if (name === "wasm/controller.js") {
            return "wasm/controller.js";
          }
          return `${name}-[hash].js`;
        },
      },
    },
  },
});
