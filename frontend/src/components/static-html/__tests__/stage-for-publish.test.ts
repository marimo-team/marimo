/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MAX_PUBLISH_BYTES, stageForPublish } from "../stage-for-publish";

const PENDING = {
  pendingId: "pend_1",
  presignedUrl: "https://bucket.example/pending/pend_1?sig=abc",
  claimUrl:
    "https://molab.marimo.io/artifacts/upload?pending=pend_1&name=nb.html",
  expiresAt: "2026-01-01T00:00:00Z",
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("stageForPublish", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  it("reserves a pending upload, PUTs the export, and returns the claim URL", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(PENDING))
      .mockResolvedValueOnce(new Response(null, { status: 200 }));

    const claimUrl = await stageForPublish("nb.html", "<html>hi</html>");

    expect(claimUrl).toBe(PENDING.claimUrl);
    expect(fetchMock).toHaveBeenCalledTimes(2);

    const [stageUrl, stageInit] = fetchMock.mock.calls[0];
    expect(String(stageUrl)).toMatch(/\/api\/artifacts\/pending$/);
    expect(stageInit?.method).toBe("POST");
    expect(JSON.parse(String(stageInit?.body))).toEqual({
      fileName: "nb.html",
      fileSize: new Blob(["<html>hi</html>"]).size,
    });

    const [putUrl, putInit] = fetchMock.mock.calls[1];
    expect(putUrl).toBe(PENDING.presignedUrl);
    expect(putInit?.method).toBe("PUT");
    expect(putInit?.body).toBeInstanceOf(Blob);
  });

  it("surfaces the server's error message when staging is rejected", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ error: "Only .html or .htm files are supported" }, 400),
    );

    await expect(stageForPublish("nb.txt", "x")).rejects.toThrow(
      "Only .html or .htm files are supported",
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("explains a 429 when the body carries no message", async () => {
    fetchMock.mockResolvedValueOnce(new Response("", { status: 429 }));

    await expect(stageForPublish("nb.html", "x")).rejects.toThrow(
      "Too many uploads, try again later",
    );
  });

  it("falls back to a generic message for other bodiless failures", async () => {
    fetchMock.mockResolvedValueOnce(new Response("", { status: 500 }));

    await expect(stageForPublish("nb.html", "x")).rejects.toThrow(
      "Failed to prepare the upload",
    );
  });

  it("fails when the presigned PUT is rejected", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(PENDING))
      .mockResolvedValueOnce(new Response(null, { status: 403 }));

    await expect(stageForPublish("nb.html", "x")).rejects.toThrow(
      "Failed to upload the notebook export",
    );
  });

  it("rejects exports over the size limit before touching the network", async () => {
    // Stub Blob so the test doesn't allocate 100 MB.
    const RealBlob = globalThis.Blob;
    vi.stubGlobal(
      "Blob",
      class extends RealBlob {
        override get size() {
          return MAX_PUBLISH_BYTES + 1;
        }
      },
    );

    await expect(stageForPublish("nb.html", "x")).rejects.toThrow(
      "File is too large. Maximum size is 100 MB.",
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
