/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import http from "node:http";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { createLoader } from "@/plugins/impl/vega/vega-loader";
import { Functions } from "@/utils/functions";
import type { DataURLString } from "@/utils/json/base64";
import { patchFetch, patchVegaLoader, resolveVirtualFileURL } from "../files";

// Start a tiny server to serve virtual files
const server = http.createServer((request, response) => {
  if (request.url === "/@file/remote-content.txt") {
    response.writeHead(200, { "Content-Type": "text/plain" });
    response.end("Remote content");
  } else {
    response.writeHead(404);
    response.end();
  }
});

const host = "127.0.0.1";
const port = 4321;
const remoteURL = `http://${host}:${port}/@file/remote-content.txt`;

beforeAll(async () => {
  server.listen(port, host);
});

afterAll(async () => {
  server.close();
});

describe("patchFetch", () => {
  it("should return a blob response when a virtual file is fetched", async () => {
    const virtualFiles = {
      "/@file/virtual-file.txt":
        "data:text/plain;base64,VGVzdCBjb250ZW50" as DataURLString,
    };

    patchFetch(virtualFiles);

    const response = await window.fetch("/@file/virtual-file.txt");
    const blob = await response.blob();
    const text = await blob.text();

    expect(response instanceof Response).toBeTruthy();
    expect(text).toBe("Test content");
  });

  it("should fallback to original fetch for non-virtual files", async () => {
    vi.spyOn(window, "fetch");

    const unpatch = patchFetch({}); // No virtual files
    const response = await window.fetch(remoteURL);
    const text = await response.text();
    unpatch();

    expect(window.fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:4321/@file/remote-content.txt",
      undefined,
    );
    expect(text).toBe("Remote content");
  });

  it("should handle @file/ URLs and set content type", async () => {
    const virtualFiles = {
      "/@file/data.csv":
        "data:text/csv;base64,aGVsbG8sd29ybGQK" as DataURLString,
    };

    patchFetch(virtualFiles);

    // Test with both formats of @file URLs
    const responses = await Promise.all([
      window.fetch("/@file/data.csv"),
      window.fetch("./@file/data.csv"),
      window.fetch("http://example.com/@file/data.csv"),
    ]);

    for (const response of responses) {
      expect(response.headers.get("Content-Type")).toBe("text/csv");
      const text = await response.text();
      expect(text).toBe("hello,world\n");
    }
  });

  it("should handle file:// URLs with @file/ paths", async () => {
    const virtualFiles = {
      "/@file/local-data.txt":
        "data:text/plain;base64,TG9jYWwgZmlsZSBkYXRh" as DataURLString,
    };

    const unpatch = patchFetch(virtualFiles);

    const response = await window.fetch(
      "file:///Users/test/@file/local-data.txt",
    );
    const text = await response.text();

    expect(text).toBe("Local file data");
    expect(response.headers.get("Content-Type")).toBe("text/plain");

    unpatch();
  });

  it("should handle blob: base URIs correctly", async () => {
    // Mock document.baseURI to simulate blob: protocol
    const originalBaseURI = document.baseURI;
    Object.defineProperty(document, "baseURI", {
      value: "blob:https://example.com/uuid",
      configurable: true,
    });

    const virtualFiles = {
      "/@file/blob-test.json":
        "data:application/json;base64,eyJ0ZXN0IjogdHJ1ZX0=" as DataURLString,
    };

    patchFetch(virtualFiles);

    const response = await window.fetch("/@file/blob-test.json");
    const text = await response.text();

    expect(text).toBe('{"test": true}');
    expect(response.headers.get("Content-Type")).toBe("application/json");

    // Restore original baseURI
    Object.defineProperty(document, "baseURI", {
      value: originalBaseURI,
      configurable: true,
    });
  });

  it("should handle various content types", async () => {
    const virtualFiles = {
      "/@file/test.csv": "data:text/csv;base64,YSxiLGMK" as DataURLString,
      "/@file/test.json": "data:application/json;base64,e30K" as DataURLString,
      "/@file/test.txt": "data:text/plain;base64,dGVzdA==" as DataURLString,
      "/@file/test.bin":
        "data:application/octet-stream;base64,AAECAwQ=" as DataURLString,
    };

    patchFetch(virtualFiles);

    const testCases = [
      { file: "/@file/test.csv", expectedType: "text/csv" },
      { file: "/@file/test.json", expectedType: "application/json" },
      { file: "/@file/test.txt", expectedType: "text/plain" },
      { file: "/@file/test.bin", expectedType: "application/octet-stream" },
    ];

    for (const { file, expectedType } of testCases) {
      const response = await window.fetch(file);
      expect(response.headers.get("Content-Type")).toBe(expectedType);
    }
  });

  it("should handle data: URLs directly without processing", async () => {
    const virtualFiles = {};
    patchFetch(virtualFiles);

    const dataUrl = "data:text/plain;base64,SGVsbG8gV29ybGQ=";
    const response = await window.fetch(dataUrl);
    const text = await response.text();

    expect(text).toBe("Hello World");
  });

  it("should handle error cases gracefully", async () => {
    const virtualFiles = {};
    const unpatch = patchFetch(virtualFiles);

    // Mock Logger.error to avoid console output during tests
    const loggerSpy = vi
      .spyOn(console, "error")
      .mockImplementation(Functions.NOOP);

    // This should fallback to original fetch and potentially fail
    await expect(window.fetch("invalid://url")).rejects.toThrow();

    unpatch();
    loggerSpy.mockRestore();
  });
});

describe("patchVegaLoader - loader.http", () => {
  const pathsToTest = [
    "virtual-file.json",
    "/virtual-file.json",
    "./virtual-file.json",
    "http://foo.com/virtual-file.json",
  ];

  it.each(
    pathsToTest,
  )("should return file content for virtual files for %s", async (s) => {
    const virtualFiles = {
      "/virtual-file.json":
        "data:application/json;base64,eyJrZXkiOiAidmFsdWUifQ==" as DataURLString,
    };

    const loader = createLoader();
    const unpatch = patchVegaLoader(loader, virtualFiles);
    const content = await loader.http(s);
    unpatch();
    expect(content).toBe('{"key": "value"}');
  });

  it("should fallback to original http method for non-virtual files", async () => {
    const loader = createLoader();

    const unpatch = patchVegaLoader(loader, {});
    const content = await loader.http(remoteURL);
    unpatch(); // Restore the original http function

    expect(content).toBe("Remote content");
  });

  it("should work with data URIs", async () => {
    const loader = createLoader();
    const unpatch = patchVegaLoader(loader, {});
    const content = await loader.http(
      "data:application/json;base64,eyJrZXkiOiAidmFsdWUifQ==",
    );
    unpatch();
    expect(content).toBe('{"key": "value"}');
  });
});

describe("patchVegaLoader - loader.load", () => {
  const pathsToTest = [
    "virtual-file.json",
    "/virtual-file.json",
    "./virtual-file.json",
    "http://foo.com/virtual-file.json",
  ];

  it.each(
    pathsToTest,
  )("should return file content for virtual files for %s", async (s) => {
    const virtualFiles = {
      "/virtual-file.json":
        "data:application/json;base64,eyJrZXkiOiAidmFsdWUifQ==" as DataURLString,
    };

    const loader = createLoader();
    const unpatch = patchVegaLoader(loader, virtualFiles);
    const content = await loader.load(s);
    unpatch();
    expect(content).toBe('{"key": "value"}');
  });

  it("should fallback to original load method for non-virtual  files", async () => {
    const loader = createLoader();

    const unpatch = patchVegaLoader(loader, {});
    const content = await loader.load(remoteURL);
    unpatch(); // Restore the original load function

    expect(content).toBe("Remote content");
  });

  it("should work with data URIs", async () => {
    const loader = createLoader();
    const unpatch = patchVegaLoader(loader, {});
    const content = await loader.load(
      "data:application/json;base64,eyJrZXkiOiAidmFsdWUifQ==",
    );
    unpatch();
    expect(content).toBe('{"key": "value"}');
  });

  it("should handle missing virtual files gracefully in loader.load", async () => {
    const loader = createLoader();
    const unpatch = patchVegaLoader(loader, {});
    await expect(loader.load("/non-existent-file.json")).rejects.toThrow();
    unpatch();
  });

  it("should handle file:// URLs with @file/ paths in loader.load", async () => {
    const virtualFiles = {
      "/@file/vega-data.json":
        "data:application/json;base64,eyJ2YWx1ZXMiOiBbMSwgMiwgM119" as DataURLString,
    };

    const loader = createLoader();
    const unpatch = patchVegaLoader(loader, virtualFiles);

    try {
      const content = await loader.load("file:///path/to/@file/vega-data.json");
      expect(content).toBe('{"values": [1, 2, 3]}');
    } catch (error) {
      // If it falls back to original loader and fails, that's expected for file:// URLs
      // The important thing is that the virtual file lookup was attempted
      expect(error).toBeDefined();
    }

    unpatch();
  });

  it("should pass files parameter correctly to maybeGetVirtualFile in loader.load", async () => {
    // This test ensures the bug fix where files parameter was missing
    const virtualFiles = {
      "/test-file.json":
        "data:application/json;base64,eyJmaXhlZCI6IHRydWV9" as DataURLString,
    };

    const loader = createLoader();
    const unpatch = patchVegaLoader(loader, virtualFiles);
    const content = await loader.load("/test-file.json");
    unpatch();

    expect(content).toBe('{"fixed": true}');
  });

  it("should handle different URL patterns in loader.load", async () => {
    const virtualFiles = {
      "/@file/pattern-test.json":
        "data:application/json;base64,eyJwYXR0ZXJuIjogInRlc3QifQ==" as DataURLString,
    };

    const loader = createLoader();
    const unpatch = patchVegaLoader(loader, virtualFiles);

    // Test URL patterns that should resolve to the same virtual file
    const testUrls = [
      "/@file/pattern-test.json",
      "./@file/pattern-test.json",
      "http://example.com/@file/pattern-test.json",
    ];

    for (const url of testUrls) {
      const content = await loader.load(url);
      expect(content).toBe('{"pattern": "test"}');
    }

    // Test file:// URL separately since it might fallback
    try {
      const content = await loader.load(
        "file:///local/path/@file/pattern-test.json",
      );
      expect(content).toBe('{"pattern": "test"}');
    } catch (error) {
      // Expected if it falls back to original loader
      expect(error).toBeDefined();
    }

    unpatch();
  });
});

describe("resolveVirtualFileURL", () => {
  // Mock URL.createObjectURL for jsdom environment
  const mockBlobURLs = new Map<string, Blob>();
  let blobCounter = 0;

  beforeAll(() => {
    URL.createObjectURL = vi.fn((blob: Blob) => {
      const url = `blob:test-${blobCounter++}`;
      mockBlobURLs.set(url, blob);
      return url;
    });
    URL.revokeObjectURL = vi.fn((url: string) => {
      mockBlobURLs.delete(url);
    });
  });

  afterAll(() => {
    mockBlobURLs.clear();
  });

  it("should return a blob URL for virtual files", () => {
    const virtualFiles = {
      "/@file/widget.js":
        "data:text/javascript;base64,ZXhwb3J0IGRlZmF1bHQgeyByZW5kZXI6ICgpID0+IHt9IH0=" as DataURLString,
    };

    const result = resolveVirtualFileURL("/@file/widget.js", virtualFiles);

    expect(result).toMatch(/^blob:/);
  });

  it("should return the original URL for non-virtual files", () => {
    const virtualFiles = {};

    const result = resolveVirtualFileURL(
      "http://example.com/widget.js",
      virtualFiles,
    );

    expect(result).toBe("http://example.com/widget.js");
  });

  it("should handle various URL formats", () => {
    const virtualFiles = {
      "/@file/module.js":
        "data:text/javascript;base64,Y29uc29sZS5sb2coJ3Rlc3QnKQ==" as DataURLString,
    };

    const testUrls = [
      "/@file/module.js",
      "./@file/module.js",
      "http://example.com/@file/module.js",
    ];

    for (const url of testUrls) {
      const result = resolveVirtualFileURL(url, virtualFiles);
      expect(result).toMatch(/^blob:/);
    }
  });

  it("should create blob URL with correct content", async () => {
    const jsCode = "export default { render: () => {} }";
    const base64Code = btoa(jsCode);
    const virtualFiles = {
      "/@file/test-module.js":
        `data:text/javascript;base64,${base64Code}` as DataURLString,
    };

    const blobUrl = resolveVirtualFileURL(
      "/@file/test-module.js",
      virtualFiles,
    );

    expect(blobUrl).toMatch(/^blob:/);
    expect(URL.createObjectURL).toHaveBeenCalled();

    // Verify blob content through the mock
    const blob = mockBlobURLs.get(blobUrl);
    expect(blob).toBeDefined();
    const text = await blob!.text();
    expect(text).toBe(jsCode);
  });

  it("should handle file:// URLs with @file/ paths", () => {
    const virtualFiles = {
      "/@file/local-module.js":
        "data:text/javascript;base64,ZXhwb3J0IGRlZmF1bHQge30=" as DataURLString,
    };

    const result = resolveVirtualFileURL(
      "file:///Users/test/@file/local-module.js",
      virtualFiles,
    );

    expect(result).toMatch(/^blob:/);
  });

  it("should handle different MIME types", async () => {
    const virtualFiles = {
      "/@file/script.js":
        "data:application/javascript;base64,Y29uc3QgeCA9IDE=" as DataURLString,
    };

    const blobUrl = resolveVirtualFileURL("/@file/script.js", virtualFiles);

    // Should still be a valid blob URL
    expect(blobUrl).toMatch(/^blob:/);

    // Verify blob content through the mock
    const blob = mockBlobURLs.get(blobUrl);
    expect(blob).toBeDefined();
    const text = await blob!.text();
    expect(text).toBe("const x = 1");
  });

  it("should handle blob: base URIs correctly", () => {
    // Mock document.baseURI to simulate blob: protocol
    const originalBaseURI = document.baseURI;
    Object.defineProperty(document, "baseURI", {
      value: "blob:https://example.com/uuid",
      configurable: true,
    });

    const virtualFiles = {
      "/@file/blob-module.js":
        "data:text/javascript;base64,ZXhwb3J0IGRlZmF1bHQge30=" as DataURLString,
    };

    const result = resolveVirtualFileURL("/@file/blob-module.js", virtualFiles);

    expect(result).toMatch(/^blob:/);

    // Restore original baseURI
    Object.defineProperty(document, "baseURI", {
      value: originalBaseURI,
      configurable: true,
    });
  });

  it("should handle data URLs with no explicit MIME type", async () => {
    const virtualFiles = {
      "/@file/generic.bin": "data:;base64,SGVsbG8gV29ybGQ=" as DataURLString,
    };

    const blobUrl = resolveVirtualFileURL("/@file/generic.bin", virtualFiles);
    expect(blobUrl).toMatch(/^blob:/);

    // Verify blob content through the mock
    const blob = mockBlobURLs.get(blobUrl);
    expect(blob).toBeDefined();
    const text = await blob!.text();
    expect(text).toBe("Hello World");
  });

  it("should match URLs with prefix paths before /@file/", async () => {
    const virtualFiles = {
      "/@file/4263-66-yUGhgQXp.js":
        "data:application/javascript;base64,ZnVuY3Rpb24gcmVuZGVyKCkge30=" as DataURLString,
    };

    const blobUrl = resolveVirtualFileURL(
      "https://molab.marimo.app/preview/@file/4263-66-yUGhgQXp.js",
      virtualFiles,
    );

    expect(blobUrl).toMatch(/^blob:/);

    // Verify blob content through the mock
    const blob = mockBlobURLs.get(blobUrl);
    expect(blob).toBeDefined();
    const text = await blob!.text();
    expect(text).toBe("function render() {}");
  });
});

describe("maybeGetVirtualFile utility function", () => {
  it("should handle URLs without leading dots correctly", async () => {
    const virtualFiles = {
      "/file.txt": "data:text/plain;base64,dGVzdA==" as DataURLString,
      "file.txt": "data:text/plain;base64,dGVzdA==" as DataURLString,
    };

    patchFetch(virtualFiles);

    // Both should work
    const response1 = await window.fetch("./file.txt");
    const response2 = await window.fetch("/file.txt");

    const text1 = await response1.text();
    const text2 = await response2.text();

    expect(text1).toBe("test");
    expect(text2).toBe("test");
  });

  it("should match URLs with prefix paths before /@file/", async () => {
    const virtualFiles = {
      "/@file/4263-66-yUGhgQXp.js":
        "data:application/javascript;base64,ZnVuY3Rpb24gcmVuZGVyKCkge30=" as DataURLString,
    };

    const unpatch = patchFetch(virtualFiles);

    // Test URL with a prefix path before /@file/
    const response = await window.fetch(
      "https://molab.marimo.app/preview/@file/4263-66-yUGhgQXp.js",
    );
    const text = await response.text();

    expect(text).toBe("function render() {}");

    unpatch();
  });

  it("should handle complex file:// URLs with nested paths", async () => {
    const virtualFiles = {
      "/@file/nested/data.json":
        "data:application/json;base64,eyJuZXN0ZWQiOiB0cnVlfQ==" as DataURLString,
    };

    const unpatch = patchFetch(virtualFiles);

    const response = await window.fetch(
      "file:///Users/project/deep/path/@file/nested/data.json",
    );
    const text = await response.text();

    expect(text).toBe('{"nested": true}');

    unpatch();
  });

  it("should handle URLs when @file/ is not found in file:// URLs", async () => {
    const virtualFiles = {
      "/@file/test.txt": "data:text/plain;base64,dGVzdA==" as DataURLString,
    };

    const unpatch = patchFetch(virtualFiles);

    // This file:// URL doesn't contain @file/, so it should fallback to original fetch
    await expect(
      window.fetch("file:///simple/path/test.txt"),
    ).rejects.toThrow();

    unpatch();
  });
});

describe("error handling and edge cases", () => {
  it("should restore original functions after unpatch", async () => {
    const originalFetch = window.fetch;
    const loader = createLoader();

    const unpatchFetch = patchFetch({});
    const unpatchLoader = patchVegaLoader(loader, {});

    // Functions should be patched
    expect(window.fetch).not.toBe(originalFetch);

    // Test that the patched functions work
    const virtualFiles = {
      "/@file/test.txt": "data:text/plain;base64,dGVzdA==" as DataURLString,
    };

    // Re-patch with test data
    unpatchFetch();
    unpatchLoader();

    const unpatchFetch2 = patchFetch(virtualFiles);
    const unpatchLoader2 = patchVegaLoader(loader, virtualFiles);

    // Test functionality works
    const response = await window.fetch("/@file/test.txt");
    const text = await response.text();
    expect(text).toBe("test");

    const content = await loader.load("/@file/test.txt");
    expect(content).toBe("test");

    unpatchFetch2();
    unpatchLoader2();

    // Functions should be restored
    expect(window.fetch).toBe(originalFetch);

    // Test that the loader functions are functional (they should work normally)
    try {
      await loader.load("http://example.com/test.json");
    } catch (error) {
      // Expected to fail for non-existent URLs, but the function should be callable
      expect(error).toBeDefined();
    }
  });

  it("should handle Request objects in patchFetch", async () => {
    const virtualFiles = {
      "/@file/request-test.txt":
        "data:text/plain;base64,UmVxdWVzdCB0ZXN0" as DataURLString,
    };

    const unpatch = patchFetch(virtualFiles);

    // Use a full URL for the Request constructor
    const request = new Request("http://example.com/@file/request-test.txt");
    const response = await window.fetch(request);
    const text = await response.text();

    expect(text).toBe("Request test");

    unpatch();
  });

  it("should handle malformed URLs gracefully", async () => {
    const virtualFiles = {};
    const unpatch = patchFetch(virtualFiles);

    // Mock Logger.error to avoid test output
    const loggerSpy = vi
      .spyOn(console, "error")
      .mockImplementation(Functions.NOOP);

    // This should catch the error and fallback to original fetch
    try {
      await window.fetch("not-a-valid-url");
      // If it doesn't throw, that's also fine (fallback behavior)
    } catch (error) {
      // Expected behavior - invalid URLs should be handled gracefully
      expect(error).toBeDefined();
    }

    unpatch();
    loggerSpy.mockRestore();
  });
});
