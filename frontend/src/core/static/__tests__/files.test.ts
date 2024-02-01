/* Copyright 2024 Marimo. All rights reserved. */
import { describe, afterEach, expect, it, vi } from "vitest";
import { patchFetch, patchVegaLoader } from "../files";
import { Base64String } from "@/utils/json/base64";

describe("patchFetch", () => {
  const originalFetch = window.fetch;

  afterEach(() => {
    window.fetch = originalFetch; // Restore original fetch after each test
  });

  it("should return a blob response when a virtual file is fetched", async () => {
    const virtualFiles = {
      "/@file/virtual-file.txt": {
        base64: "data:text/plain;base64,VGVzdCBjb250ZW50" as Base64String,
      },
    };

    patchFetch(virtualFiles);

    const response = await fetch("/@file/virtual-file.txt");
    const blob = await response.blob();
    const text = await blob.text();

    expect(response instanceof Response).toBeTruthy();
    expect(text).toBe("Test content");
  });

  it("should fallback to original fetch for non-virtual files", async () => {
    const mockResponse = new Response("Not a virtual file");
    window.fetch = vi.fn().mockResolvedValue(mockResponse);

    const unpatch = patchFetch({}); // No virtual files

    const response = await fetch("/@file/non-virtual-file.txt");
    const text = await response.text();

    unpatch();
    expect(window.fetch).toHaveBeenCalledWith(
      "/@file/non-virtual-file.txt",
      undefined,
    );
    expect(text).toBe("Not a virtual file");
  });
});

describe("patchVegaLoader", () => {
  it("should return file content for virtual files", async () => {
    const virtualFiles = {
      "virtual-file.json": {
        base64:
          "data:application/json;base64,eyJrZXkiOiAidmFsdWUifQ==" as Base64String,
      },
    };

    const loader = {
      http: vi.fn((url) => Promise.resolve(`Original content for ${url}`)),
    };
    patchVegaLoader(loader, virtualFiles);

    const content = await loader.http("virtual-file.json");
    expect(content).toBe('{"key": "value"}');
  });

  it("should fallback to original http method for non-virtual files", async () => {
    const loader = {
      http: vi.fn((url) => Promise.resolve(`Original content for ${url}`)),
    };

    const unpatch = patchVegaLoader(loader, {});
    const content = await loader.http("non-virtual-file.json");
    unpatch(); // Restore the original http function

    expect(content).toBe("Original content for non-virtual-file.json");
    expect(loader.http).toHaveBeenCalledWith("non-virtual-file.json");
  });
});
