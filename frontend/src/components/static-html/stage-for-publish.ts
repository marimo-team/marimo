/* Copyright 2026 Marimo. All rights reserved. */

import { Constants } from "@/core/constants";

interface PendingUploadResponse {
  pendingId: string;
  presignedUrl: string;
  claimUrl: string;
  expiresAt: string;
}

// Keep in sync with molab.
export const MAX_PUBLISH_BYTES = 100 * 1024 * 1024;

/**
 * Stage an HTML export for publishing on molab: reserve a pending upload,
 * PUT the bytes to the presigned URL, and return the claim URL where the
 * user finishes publishing after signing in.
 */
export async function stageForPublish(
  fileName: string,
  html: string,
): Promise<string> {
  const blob = new Blob([html], { type: "text/html" });
  if (blob.size > MAX_PUBLISH_BYTES) {
    throw new Error("File is too large. Maximum size is 100 MB.");
  }

  const staged = await fetch(`${Constants.molab}/api/artifacts/pending`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fileName, fileSize: blob.size }),
  });
  if (!staged.ok) {
    const body = (await staged.json().catch(() => null)) as {
      error?: string;
    } | null;
    throw new Error(
      body?.error ??
        (staged.status === 429
          ? "Too many uploads, try again later"
          : "Failed to prepare the upload"),
    );
  }
  const { presignedUrl, claimUrl } =
    (await staged.json()) as PendingUploadResponse;

  // The presigned PUT is capped to the declared size; the browser sends the
  // matching Content-Length automatically from the blob.
  const put = await fetch(presignedUrl, { method: "PUT", body: blob });
  if (!put.ok) {
    throw new Error("Failed to upload the notebook export");
  }

  return claimUrl;
}
