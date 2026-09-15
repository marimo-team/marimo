/* Copyright 2026 Marimo. All rights reserved. */

import { downloadExportedFile } from "@/utils/download";
import { getExportLayout } from "../export/layout";
import { getRequestClient } from "../network/requests";
import { VirtualFileTracker } from "./virtual-file-tracker";

/**
 * Downloads the current notebook as an HTML file.
 */
export async function downloadAsHTML(opts: { includeCode: boolean }) {
  const client = getRequestClient();
  const { includeCode } = opts;
  const exportedFile = await client.exportAsHTML({
    download: true,
    includeCode: includeCode,
    files: VirtualFileTracker.INSTANCE.filenames(),
    layout: await getExportLayout(),
  });

  downloadExportedFile(exportedFile);
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
