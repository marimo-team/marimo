/* Copyright 2024 Marimo. All rights reserved. */
import { exportHTML } from "../network/requests";
import { downloadBlob } from "@/utils/download";
import { Paths } from "@/utils/paths";
import { VirtualFileTracker } from "./virtual-file-tracker";

/**
 * Downloads the current notebook as an HTML file.
 */
export async function downloadAsHTML(opts: { filename: string }) {
  const { filename } = opts;
  const html = await exportHTML({
    download: true,
    includeCode: true,
    files: VirtualFileTracker.INSTANCE.filenames(),
  });
  const filenameWithoutPath = Paths.basename(filename) ?? "notebook.py";
  const filenameWithoutExtension =
    filenameWithoutPath.split(".").shift() ?? "app";

  downloadBlob(
    new Blob([html], { type: "text/html" }),
    `${filenameWithoutExtension}.html`,
  );
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
