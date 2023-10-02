/* Copyright 2023 Marimo. All rights reserved. */
import { defineConfig, Plugin } from "vite";
import react from "@vitejs/plugin-react-swc";
import tsconfigPaths from "vite-tsconfig-paths";

const htmlDevPlugin = (): Plugin => {
  return {
    apply: "serve",
    name: "html-transform",
    transformIndexHtml(html) {
      return html
        .replace(`{{ filename }}`, `dev-mode`)
        .replace(`{{ mode }}`, `"edit"`)
        .replace(
          `{{ user_config }}`,
          JSON.stringify({
            completion: {
              activate_on_typing: false,
              copilot: true,
            },
            save: {
              autosave: "off",
              autosave_delay: 0,
              auto_instantiate: true,
            },
            keymap: {
              preset: "default",
            },
            experimental: {
              theming: true,
              layouts: true,
            },
          })
        )
        .replace(`{{ app_config }}`, JSON.stringify({}))
        .replace(`{{ title }}`, `dev-mode`);
    },
  };
};

const SERVER_PORT = process.env.SERVER_PORT || 2718;

// https://vitejs.dev/config/
export default defineConfig({
  server: {
    host: "localhost",
    port: 3000,
    proxy: {
      "/api": {
        target: `http://localhost:${SERVER_PORT}`,
        changeOrigin: true,
      },
      "/iosocket": {
        target: `ws://localhost:${SERVER_PORT}`,
        ws: true,
        changeOrigin: true,
        headers: {
          origin: `http://localhost:${SERVER_PORT}`,
        },
      },
    },
  },
  resolve: {
    dedupe: ["react", "react-dom", "@emotion/react", "@emotion/cache"],
  },
  plugins: [
    htmlDevPlugin(),
    react({
      tsDecorators: true,
      plugins: [["@swc-jotai/react-refresh", {}]],
    }),
    tsconfigPaths(),
  ],
});
