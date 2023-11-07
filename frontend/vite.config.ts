/* Copyright 2023 Marimo. All rights reserved. */
import { defineConfig, Plugin } from "vite";
import react from "@vitejs/plugin-react-swc";
import tsconfigPaths from "vite-tsconfig-paths";
import { JSDOM } from "jsdom";

const SERVER_PORT = process.env.SERVER_PORT || 2718;
const isDev = process.env.NODE_ENV === "development";

const htmlDevPlugin = (): Plugin => {
  return {
    apply: "serve",
    name: "html-transform",
    transformIndexHtml: async (html) => {
      // fetch html from server
      const serverHtml = await fetch(`http://localhost:${SERVER_PORT}/`).then(
        (res) => res.text()
      );

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
        target: `http://localhost:${SERVER_PORT}`,
        changeOrigin: true,
      },
      "/@file": {
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
      plugins: isDev ? [["@swc-jotai/react-refresh", {}]] : undefined,
    }),
    tsconfigPaths(),
  ],
});
