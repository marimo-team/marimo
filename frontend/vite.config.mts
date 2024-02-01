/* Copyright 2024 Marimo. All rights reserved. */
import { defineConfig, Plugin } from "vite";
import react from "@vitejs/plugin-react-swc";
import tsconfigPaths from "vite-tsconfig-paths";
import { JSDOM } from "jsdom";

const SERVER_PORT = process.env.SERVER_PORT || 2718;
const HOST = process.env.HOST || "127.0.0.1";
const TARGET = `http://${HOST}:${SERVER_PORT}`;
const isDev = process.env.NODE_ENV === "development";
const isStorybook = process.env.npm_lifecycle_script?.includes("storybook");

const htmlDevPlugin = (): Plugin => {
  return {
    apply: "serve",
    name: "html-transform",
    transformIndexHtml: async (html) => {
      if (isStorybook) {
        return html;
      }

      // fetch html from server
      const serverHtmlResponse = await fetch(TARGET);
      const serverHtml = await serverHtmlResponse.text();

      const serverDoc = new JSDOM(serverHtml).window.document;
      const devDoc = new JSDOM(html).window.document;

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
          throw new Error(`Element ${id} not found.`);
        }
        element.remove();
      });

      // copy from server
      copyElements.forEach((id) => {
        const element = serverDoc.querySelector(id);
        if (!element) {
          throw new Error(`Element ${id} not found.`);
        }
        devDoc.head.append(element);
      });

      return devDoc.documentElement.outerHTML;
    },
  };
};

// https://vitejs.dev/config/
export default defineConfig({
  server: {
    host: "localhost",
    port: 3000,
    proxy: {
      "/api": {
        target: TARGET,
        changeOrigin: true,
      },
      "/@file": {
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
    },
  },
  resolve: {
    dedupe: ["react", "react-dom", "@emotion/react", "@emotion/cache"],
  },
  plugins: [
    htmlDevPlugin(),
    react({
      tsDecorators: true,
      plugins: isDev
        ? [
            // Fails on latest Vite
            // ["@swc-jotai/react-refresh", {}]
          ]
        : undefined,
    }),
    tsconfigPaths(),
  ],
});
