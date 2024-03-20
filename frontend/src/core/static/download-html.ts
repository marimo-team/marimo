/* Copyright 2024 Marimo. All rights reserved. */
import { Objects } from "@/utils/objects";
import { NotebookState, getNotebook } from "../cells/cells";
import { getMarimoVersion } from "../dom/marimo-tag";
import { downloadVirtualFiles } from "./files";
import { StaticVirtualFiles } from "./types";
import { serializeJsonToBase64 } from "@/utils/json/base64";
import { readCode } from "../network/requests";
import { downloadBlob } from "@/utils/download";
import { Paths } from "@/utils/paths";

// For Testing:
// Flip this to `true` to use local assets instead of CDN
// This should be `false` for production
const ENABLE_LOCAL_ASSETS = false;

/**
 * Downloads the current notebook as an HTML file.
 */
export async function createStaticHTMLNotebook() {
  const notebook = getNotebook();
  const version = getMarimoVersion();

  const assetUrl =
    ENABLE_LOCAL_ASSETS ||
    process.env.NODE_ENV === "development" ||
    process.env.NODE_ENV === "test"
      ? window.location.origin
      : `https://cdn.jsdelivr.net/npm/@marimo-team/frontend@${version}/dist`;

  const codeResponse = await readCode();

  const html = constructHTML({
    notebookState: notebook,
    version: version,
    assetUrl: assetUrl,
    existingDocument: document,
    files: await downloadVirtualFiles(),
    code: codeResponse.contents,
  });

  return html;
}

/**
 * Downloads the current notebook as an HTML file.
 */
export async function downloadAsHTML(opts: { filename: string }) {
  const { filename } = opts;
  const html = await createStaticHTMLNotebook();

  const filenameWithoutPath = Paths.basename(filename) ?? "notebook.py";
  const filenameWithoutExtension =
    filenameWithoutPath.split(".").shift() ?? "app";

  downloadBlob(
    new Blob([html], { type: "text/html" }),
    `${filenameWithoutExtension}.html`,
  );
}

/**
 * Constructs HTML for the a static rendering of the page.
 */
export function constructHTML(opts: {
  version: string;
  notebookState: Pick<NotebookState, "cellIds" | "cellData" | "cellRuntime">;
  assetUrl: string;
  files: StaticVirtualFiles;
  existingDocument: Document;
  code: string;
}) {
  const { version, notebookState, assetUrl, existingDocument, files, code } =
    opts;

  const staticHead = existingDocument.head.cloneNode(true) as HTMLHeadElement;
  // Remove fonts, that contain as="font"
  staticHead.querySelectorAll("link[as=font]").forEach((el) => el.remove());

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
      <base href="/">
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
          cellData: Objects.mapValues(
            notebookState.cellData,
            serializeJsonToBase64,
          ),
          cellRuntime: Objects.mapValues(
            notebookState.cellRuntime,
            serializeJsonToBase64,
          ),
        })};
        window.__MARIMO_STATIC__.assetUrl = "${assetUrl}";
        window.__MARIMO_STATIC__.files = ${JSON.stringify(files)};
      </script>

      <marimo-code hidden="">
        ${encodeURIComponent(code)}
      </marimo-code>
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

  doc.head.innerHTML = `
  ${doc.head.innerHTML}
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fira+Mono:wght@400;500;700&family=Lora&family=PT+Sans:wght@400;700&display=swap" rel="stylesheet">
  `.trim();

  // add DOCTYPE back in
  return `<!DOCTYPE html>\n${doc.documentElement.outerHTML}`;
}

function updateAssetUrl(existingUrl: string, assetBaseUrl: string) {
  // Will convert: https://localhost:8080/assets/index-c78b8d10.js
  //  Or will convert ./assets/index-c78b8d10.js
  //  Or will convert /assets/index-c78b8d10.js
  // into: https://cdn.jsdelivr.net/npm/@marimo-team/frontend@0.1.43/dist/assets/index-c78b8d10.js

  // relative './...'
  if (existingUrl.startsWith("./")) {
    return `${assetBaseUrl}${existingUrl.slice(1)}`;
  }

  // relative '/...'
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

export const visibleForTesting = {
  updateAssetUrl,
};
