/* Copyright 2023 Marimo. All rights reserved. */
import { NotebookState, getNotebook } from "../cells/cells";
import { getMarimoVersion } from "../dom/marimo-tag";

// For Testing:
// Flip this to true to use local assets instead of CDN
// This should be false for production
const ENABLE_LOCAL_ASSETS = false;

/**
 * Downloads the current notebook as an HTML file.
 */
export function downloadAsHTML(opts: { filename?: string }) {
  const { filename } = opts;
  const notebook = getNotebook();
  const version = getMarimoVersion();

  const assetUrl =
    ENABLE_LOCAL_ASSETS || process.env.NODE_ENV === "development"
      ? window.location.origin
      : `https://cdn.jsdelivr.net/npm/@marimo-team/frontend@${version}/dist`;

  const html = constructHTML({
    notebookState: notebook,
    version: version,
    assetUrl: assetUrl,
    filename: filename || "notebook",
    existingDocument: document,
  });

  const url = URL.createObjectURL(new Blob([html], { type: "text/html" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename ? `${filename}.html` : "notebook.html";
  a.click();
}

/**
 * Constructs HTML for the a static rendering of the page.
 */
export function constructHTML(opts: {
  version: string;
  notebookState: Pick<NotebookState, "cellIds" | "cellData" | "cellRuntime">;
  assetUrl: string;
  filename: string;
  existingDocument: Document;
}) {
  const { version, notebookState, assetUrl, existingDocument } = opts;

  const staticHead = existingDocument.head.cloneNode(true) as HTMLHeadElement;

  const elementsFromBody = [
    "marimo-filename",
    "marimo-version",
    "marimo-user-config",
    "marimo-app-config",
  ];

  // Create initial elements
  const html = `
  <!DOCTYPE html>
  <html>
    <head>
      ${staticHead.innerHTML}
    </head>

    <body>
      <div id="root"></div>
      <marimo-mode data-mode="read" hidden=""></marimo-mode>
      ${elementsFromBody
        .map((id) => {
          const element = existingDocument.querySelector(id);
          if (!element) {
            throw new Error(`Element ${id} not found.`);
          }
          return element.outerHTML;
        })
        .join("\n")}
      <script data-marimo="true">
        window.__MARIMO_STATIC__ = {};
        window.__MARIMO_STATIC__.version = "${version}";
        window.__MARIMO_STATIC__.notebookState = ${JSON.stringify({
          cellIds: notebookState.cellIds,
          cellData: notebookState.cellData,
          cellRuntime: notebookState.cellRuntime,
        })};
        window.__MARIMO_STATIC__.assetUrl = "${assetUrl}";
      </script>
    </body>
  </html>
  `;

  const doc = new DOMParser().parseFromString(html, "text/html");

  // Copy over any stylesheets or scripts from the body that are URL based
  const body = existingDocument.body;
  const appendToBody = (element: Element) => {
    const el = element.cloneNode(true);
    if (el instanceof HTMLElement) {
      el.setAttribute("crossorigin", "anonymous");
    }
    doc.body.append(element.cloneNode(true));
  };
  body.querySelectorAll("style[href]").forEach(appendToBody);
  body.querySelectorAll("script[src]").forEach(appendToBody);
  body.querySelectorAll("link[href]").forEach(appendToBody);

  // Update scripts to point to CDN
  const scripts = doc.querySelectorAll("script");
  scripts.forEach((script) => {
    const src = script.getAttribute("src");
    if (src) {
      script.setAttribute("src", updateAssetUrl(src, assetUrl));
      script.setAttribute("crossorigin", "anonymous");
    } else if (!Object.hasOwn(script.dataset, "marimo")) {
      script.remove();
    }
  });

  // Update links to point to CDN
  const links = doc.querySelectorAll("link");
  links.forEach((link) => {
    const href = link.getAttribute("href");
    if (href) {
      link.setAttribute("href", updateAssetUrl(href, assetUrl));
      link.setAttribute("crossorigin", "anonymous");
    } else {
      link.remove();
    }
  });

  // Remove style tags
  const styles = doc.querySelectorAll("style");
  styles.forEach((style) => style.remove());

  // Handle testing with Vite
  if (process.env.NODE_ENV === "development") {
    const devScript = doc.createElement("script");
    devScript.setAttribute("type", "module");
    devScript.setAttribute("src", `${window.location.origin}/src/main.tsx`);
    doc.body.append(devScript);
  }

  return doc.documentElement.outerHTML;
}

function updateAssetUrl(existingUrl: string, assetBaseUrl: string) {
  // Will convert: https://localhost:8080/assets/index-c78b8d10.js
  // into: https://cdn.jsdelivr.net/npm/@marimo-team/frontend@0.1.43/dist/assets/index-c78b8d10.js

  // relative path
  if (existingUrl.startsWith("/")) {
    return `${assetBaseUrl}${existingUrl}`;
  }

  // absolute path
  const url = new URL(existingUrl);
  if (url.origin !== window.location.origin) {
    return `${assetBaseUrl}${url.pathname}`;
  }

  // otherwise, leave as is
  return existingUrl;
}
