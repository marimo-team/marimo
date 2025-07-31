/* Copyright 2024 Marimo. All rights reserved. */
// @vitest-environment jsdom

import http from "node:http";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { createLoader } from "@/plugins/impl/vega/vega-loader";
import type { DataURLString } from "@/utils/json/base64";
import { patchFetch, patchVegaLoader } from "../files";

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
});

describe("patchVegaLoader - loader.http", () => {
  const pathsToTest = [
    "virtual-file.json",
    "/virtual-file.json",
    "./virtual-file.json",
    "http://foo.com/virtual-file.json",
  ];

  it.each(pathsToTest)(
    "should return file content for virtual files for %s",
    async (s) => {
      const virtualFiles = {
        "/virtual-file.json":
          "data:application/json;base64,eyJrZXkiOiAidmFsdWUifQ==" as DataURLString,
      };

      const loader = createLoader();
      const unpatch = patchVegaLoader(loader, virtualFiles);
      const content = await loader.http(s);
      unpatch();
      expect(content).toBe('{"key": "value"}');
    },
  );

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

  it.each(pathsToTest)(
    "should return file content for virtual files for %s",
    async (s) => {
      const virtualFiles = {
        "/virtual-file.json":
          "data:application/json;base64,eyJrZXkiOiAidmFsdWUifQ==" as DataURLString,
      };

      const loader = createLoader();
      const unpatch = patchVegaLoader(loader, virtualFiles);
      const content = await loader.load(s);
      unpatch();
      expect(content).toBe('{"key": "value"}');
    },
  );

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
});
