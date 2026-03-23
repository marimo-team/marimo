/* Copyright 2026 Marimo. All rights reserved. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { copyImageToClipboard, isSafari } from "../copy";

describe("isSafari", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns true for Safari on macOS", () => {
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue(
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    );
    expect(isSafari()).toBe(true);
  });

  it("returns true for Safari on iOS", () => {
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue(
      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    );
    expect(isSafari()).toBe(true);
  });

  it("returns false for Chrome", () => {
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue(
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    );
    expect(isSafari()).toBe(false);
  });

  it("returns false for Chrome on iOS (CriOS)", () => {
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue(
      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/120.0.0.0 Mobile/15E148 Safari/604.1",
    );
    expect(isSafari()).toBe(false);
  });

  it("returns false for Firefox on iOS (FxiOS)", () => {
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue(
      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/120.0 Mobile/15E148 Safari/604.1",
    );
    expect(isSafari()).toBe(false);
  });

  it("returns false for Edge on iOS (EdgiOS)", () => {
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue(
      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) EdgiOS/120.0.0.0 Mobile/15E148 Safari/604.1",
    );
    expect(isSafari()).toBe(false);
  });

  it("returns false for Firefox on desktop", () => {
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue(
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
    );
    expect(isSafari()).toBe(false);
  });
});

describe("copyImageToClipboard", () => {
  let writeMock: ReturnType<typeof vi.fn>;
  let clipboardItemSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    writeMock = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: { write: writeMock },
    });

    // ClipboardItem is not available in jsdom, so we mock it
    clipboardItemSpy = vi.fn().mockImplementation((data) => ({ data }));
    vi.stubGlobal("ClipboardItem", clipboardItemSpy);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("uses blob type from response on non-Safari browsers", async () => {
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue(
      "Mozilla/5.0 Chrome/120.0.0.0 Safari/537.36",
    );

    const fakeBlob = new Blob(["fake"], { type: "image/jpeg" });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(fakeBlob, {
        headers: { "Content-Type": "image/jpeg" },
      }),
    );

    await copyImageToClipboard("https://example.com/image.jpg");

    expect(writeMock).toHaveBeenCalledOnce();
    // Non-Safari path: awaits blob, uses blob.type as key
    const arg = clipboardItemSpy.mock.calls[0][0];
    expect(arg).toHaveProperty("image/jpeg");
    expect(arg["image/jpeg"].type).toBe("image/jpeg");
  });

  it("uses image/png on Safari", async () => {
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue(
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    );

    const fakeBlob = new Blob(["fake"], { type: "image/png" });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(fakeBlob));

    await copyImageToClipboard("https://example.com/image.png");

    expect(writeMock).toHaveBeenCalledOnce();
    // Safari path: uses "image/png" key with a Promise<Blob>
    expect(clipboardItemSpy).toHaveBeenCalledWith({
      "image/png": expect.any(Promise),
    });
  });

  it("propagates fetch errors", async () => {
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue(
      "Mozilla/5.0 Chrome/120.0.0.0 Safari/537.36",
    );

    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("Network error"));

    await expect(
      copyImageToClipboard("https://example.com/image.png"),
    ).rejects.toThrow("Network error");
  });
});
