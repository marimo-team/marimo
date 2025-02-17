/* Copyright 2024 Marimo. All rights reserved. */
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";
import { JSDOM } from "jsdom";

const SERVER_PORT = process.env.SERVER_PORT || 2718;
const HOST = process.env.HOST || "127.0.0.1";
const TARGET = `http://${HOST}:${SERVER_PORT}`;
const isDev = process.env.NODE_ENV === "development";
const isStorybook = process.env.npm_lifecycle_script?.includes("storybook");
const isPyodide = process.env.PYODIDE === "true";

const htmlDevPlugin = (): Plugin => {
  return {
    apply: "serve",
    name: "html-transform",
    transformIndexHtml: async (html, ctx) => {
      if (isStorybook) {
        return html;
      }

      // Add react-scan in dev mode
      if (isDev) {
        html = html.replace(
          "<head>",
          '<head>\n<script src="https://unpkg.com/react-scan/dist/auto.global.js"></script>',
        );
      }

      if (isPyodide) {
        const modeFromUrl = ctx.originalUrl?.includes("mode=read")
          ? "read"
          : "edit";
        html = html.replace("{{ base_url }}", "");
        html = html.replace("{{ title }}", "marimo");
        html = html.replace(
          "{{ user_config }}",
          JSON.stringify({
            // Add/remove user config here while developing
            // runtime: {
            //   auto_instantiate: false,
            // },
          }),
        );
        html = html.replace("{{ app_config }}", JSON.stringify({}));
        html = html.replace("{{ server_token }}", "");
        if (process.env.VITE_MARIMO_VERSION) {
          // If VITE_MARIMO_VERSION is defined, pull the local version of marimo
          html = html.replace("{{ version }}", "local");
        } else {
          // Otherwise, pull the latest version of marimo from PyPI
          html = html.replace("{{ version }}", "latest");
        }
        html = html.replace("{{ filename }}", "notebook.py");
        html = html.replace("{{ mode }}", modeFromUrl);
        html = html.replace(/<\/head>/, "<marimo-wasm></marimo-wasm></head>");
        return html;
      }

      // fetch html from server
      let serverHtml: string;
      try {
        const serverHtmlResponse = await fetch(TARGET + ctx.originalUrl);
        if (!serverHtmlResponse.ok) {
          throw new Error("Failed to fetch");
        }
        serverHtml = await serverHtmlResponse.text();
      } catch (e) {
        console.error(
          `Failed to connect to a marimo server at ${TARGET + ctx.originalUrl}`,
        );
        console.log(`
A marimo server may not be running.
Run \x1b[32mmarimo edit --no-token --headless\x1b[0m in another terminal to start the server.

If the server is already running, make sure it is using port ${SERVER_PORT} with \x1b[1m--port=${SERVER_PORT}\x1b[0m.
        `);
        return `
        <html>
          <body style="padding: 2rem; font-family: system-ui, sans-serif; line-height: 1.5;">
            <div style="max-width: 500px; margin: 0 auto;">
              <h2 style="color: #e53e3e">Server Connection Error</h2>

              <p>
                Could not connect to marimo server at:<br/>
                <code style="background: #f7f7f7; padding: 0.2rem 0.4rem; border-radius: 4px;">
                  ${TARGET + ctx.originalUrl}
                </code>
              </p>

              <div style="background: #f7f7f7; padding: 1.5rem; border-radius: 8px;">
                <div>To start the server, run:</div>
                <code style="color: #32CD32; font-weight: 600;">
                  marimo edit --no-token --headless
                </code>
              </div>

              <p>
                If the server is already running, make sure it is using port
                <code style="font-weight: 600;">${SERVER_PORT}</code>
                with the flag
                <code style="font-weight: 600;">--port=${SERVER_PORT}</code>
              </p>
            </div>
          </body>
        </html>
        `;
      }

      const serverDoc = new JSDOM(serverHtml).window.document;
      const devDoc = new JSDOM(html).window.document;

      // Login page
      if (!serverHtml.includes("marimo-mode") && serverHtml.includes("login")) {
        return `
        <html>
          <body style="padding: 2rem; font-family: system-ui, sans-serif; line-height: 1.5;">
            <div style="max-width: 500px; margin: 0 auto;">
              <h2 style="color: #e53e3e">Authentication Not Supported</h2>

              <p>
                In development mode, please run the server without authentication:
              </p>

              <div style="background: #f7f7f7; padding: 1.5rem; border-radius: 8px;">
                <code style="color: #32CD32; font-weight: 600;">
                  marimo edit --no-token
                </code>
              </div>
            </div>
          </body>
        </html>
        `;
      }

      // copies these elements from server to dev
      const copyElements = [
        "title",
        "marimo-filename",
        "marimo-version",
        "marimo-mode",
        "marimo-user-config",
        "marimo-app-config",
        "marimo-server-token",
      ];

      // remove from dev
      copyElements.forEach((id) => {
        const element = devDoc.querySelector(id);
        if (!element) {
          console.warn(`Element ${id} not found.`);
          return;
        }
        element.remove();
      });

      // copy from server
      copyElements.forEach((id) => {
        const element = serverDoc.querySelector(id);
        if (!element) {
          console.warn(`Element ${id} not found.`);
          return;
        }
        devDoc.head.append(element);
      });

      // Copy styles
      const styles = serverDoc.querySelectorAll("style");
      styles.forEach((style) => {
        devDoc.head.append(style);
      });

      return `<!DOCTYPE html>\n${devDoc.documentElement.outerHTML}`;
    },
  };
};

const ReactCompilerConfig = {
  target: "18",
};

// https://vitejs.dev/config/
export default defineConfig({
  // This allows for a dynamic <base> tag in index.html
  base: "./",
  server: {
    host: "localhost",
    port: 3000,
    proxy: {
      "/api": {
        target: TARGET,
        changeOrigin: true,
      },
      "/auth": {
        target: TARGET,
        changeOrigin: true,
      },
      "/@file": {
        target: TARGET,
        changeOrigin: true,
      },
      "/custom.css": {
        target: TARGET,
        changeOrigin: true,
      },
      "/ws": {
        target: `ws://${HOST}:${SERVER_PORT}`,
        ws: true,
        changeOrigin: true,
        headers: {
          origin: TARGET,
        },
      },
      "/lsp": {
        target: `ws://${HOST}:${SERVER_PORT}`,
        ws: true,
        changeOrigin: true,
        headers: {
          origin: TARGET,
        },
      },
      "/terminal/ws": {
        target: `ws://${HOST}:${SERVER_PORT}`,
        ws: true,
        changeOrigin: true,
        headers: {
          origin: TARGET,
        },
      },
    },
    headers: isPyodide
      ? {
          "Cross-Origin-Opener-Policy": "same-origin",
          "Cross-Origin-Embedder-Policy": "require-corp",
        }
      : {},
  },
  define: {
    "import.meta.env.VITE_MARIMO_VERSION": process.env.VITE_MARIMO_VERSION
      ? JSON.stringify(process.env.VITE_MARIMO_VERSION)
      : JSON.stringify("latest"),
  },
  build: {
    minify: isDev ? false : "terser",
    sourcemap: isDev,
  },
  resolve: {
    dedupe: ["react", "react-dom", "@emotion/react", "@emotion/cache"],
  },
  worker: {
    format: "es",
    plugins: () => [tsconfigPaths()],
  },
  plugins: [
    htmlDevPlugin(),
    react({
      babel: {
        presets: ["@babel/preset-typescript"],
        plugins: [
          ["@babel/plugin-proposal-decorators", { legacy: true }],
          ["@babel/plugin-proposal-class-properties", { loose: true }],
          ["babel-plugin-react-compiler", ReactCompilerConfig],
        ],
      },
    }),

    tsconfigPaths(),
  ],
});
