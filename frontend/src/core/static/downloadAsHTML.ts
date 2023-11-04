/* Copyright 2023 Marimo. All rights reserved. */
import { startCase } from "lodash-es";
import { NotebookState, getNotebook } from "../state/cells";
import { getAppConfig, getUserConfig } from "../state/config";

/**
 * Downloads the current notebook as an HTML file.
 */
export function downloadAsHTML(opts: { filename?: string }) {
  const { filename } = opts;
  const notebook = getNotebook();
  const version = "0.1.43"; // TODO: Grab from <marimo-version>
  const html = constructHTML({
    notebookState: notebook,
    version: version,
    assetUrl: `https://cdn.jsdelivr.net/npm/@marimo-team/frontend@${version}/dist`,
    filename: filename || "notebook",
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
  notebookState: NotebookState;
  assetUrl: string;
  filename: string;
}) {
  const { version, notebookState, assetUrl, filename } = opts;
  const title = filename.replace(".py", "");

  return `
<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8">
    <title>${startCase(title)}</title>

    <script>
      function __resizeIframe(obj) {
        obj.style.height =
          obj.contentWindow.document.documentElement.scrollHeight + "px";
      }
    </script>
    <marimo-filename hidden>${filename}</marimo-filename>
    <marimo-mode data-mode="read" hidden></marimo-mode>
    <marimo-version data-mode="${version}" hidden></marimo-mode>
    <marimo-user-config data-config='${JSON.stringify(
      getUserConfig()
    )}' hidden></marimo-user-config>
    <marimo-app-config data-config='${JSON.stringify(
      getAppConfig()
    )}' hidden></marimo-app-config>

    ${createNewElements(assetUrl)
      .map((element) => element.outerHTML)
      .join("\n")}
  </head>

  <body>
    <div id="root"></div>
    <script>
      window.__MARIMO_STATIC__ = {};
      window.__MARIMO_STATIC__.version = "${version}";
      window.__MARIMO_STATIC__.notebookState = ${JSON.stringify({
        cellIds: notebookState.cellIds,
        cellData: notebookState.cellData,
        cellRuntime: notebookState.cellRuntime,
      })};
    </script>

    <script>
      window.__MARIMO_STATIC__.assetUrl = "${assetUrl}";
    </script>
  </body>
</html>
  `.trim();
}

/**
 * Find all assets that have the URL /assets in the path.
 */
function findAllAssets() {
  // look for src of href that starts with /assets
  const scripts = document.querySelectorAll("script[src^='/assets']");
  const links = document.querySelectorAll("link[href^='/assets']");
  // convert to array
  // eslint-disable-next-line unicorn/prefer-spread
  const scriptsArray = Array.from(scripts);
  // eslint-disable-next-line unicorn/prefer-spread
  const linksArray = Array.from(links);
  return [...scriptsArray, ...linksArray];
}

function createNewElements(assetUrl: string) {
  const assets = findAllAssets();
  const newElements = assets.map((element) => {
    const newElement = element.cloneNode(true) as HTMLElement;
    if (newElement instanceof HTMLScriptElement) {
      newElement.src = updateAssetUrl(newElement.src, assetUrl);
      newElement.crossOrigin = "anonymous";
    } else if (newElement instanceof HTMLLinkElement) {
      newElement.href = updateAssetUrl(newElement.href, assetUrl);
      newElement.crossOrigin = "anonymous";
    }
    return newElement;
  });
  return newElements;
}

function updateAssetUrl(existingUrl: string, assetBaseUrl: string) {
  // Will convert: https://localhost:8080/assets/index-c78b8d10.js
  // into: https://cdn.jsdelivr.net/npm/@marimo-team/frontend@0.1.43/dist/assets/index-c78b8d10.js

  const path = existingUrl.startsWith("/")
    ? existingUrl
    : new URL(existingUrl).pathname;
  return `${assetBaseUrl}${path}`;
}
