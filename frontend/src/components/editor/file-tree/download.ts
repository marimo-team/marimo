/* Copyright 2026 Marimo. All rights reserved. */

import { getRequestClient } from "@/core/network/requests";
import { getRuntimeManager } from "@/core/runtime/config";
import { isWasm } from "@/core/wasm/utils";
import { deserializeBlob } from "@/utils/blob";
import { downloadBlob, downloadByURL } from "@/utils/download";
import { type Base64String, base64ToDataURL } from "@/utils/json/base64";

/**
 * Download a workspace file by path.
 *
 * Over HTTP this navigates to a streaming download endpoint, so the
 * browser's download manager handles the transfer and no file contents
 * are buffered in memory. In WASM there is no HTTP server to stream
 * from; contents come over the pyodide bridge as base64 and are saved
 * via a Blob.
 */
export async function downloadFile(path: string, name: string): Promise<void> {
  if (!isWasm()) {
    const url = getRuntimeManager().formatNavigableHttpURL(
      "api/files/download",
      new URLSearchParams({ path }),
    );
    downloadByURL(url.toString(), name);
    return;
  }

  const details = await getRequestClient().sendFileDetails({ path });
  if (details.isBase64 && details.contents) {
    const blob = deserializeBlob(
      base64ToDataURL(
        details.contents as Base64String,
        details.mimeType || "application/octet-stream",
      ),
    );
    downloadBlob(blob, name);
  } else {
    downloadBlob(new Blob([details.contents || ""]), name);
  }
}
