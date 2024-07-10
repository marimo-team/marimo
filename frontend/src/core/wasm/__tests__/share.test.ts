/* Copyright 2024 Marimo. All rights reserved. */

import { expect, describe, it } from "vitest";
import { createShareableLink } from "../share";
import { compressToEncodedURIComponent } from "lz-string";

describe("createShareableLink", () => {
  it("should return a URL with the base URL when no code is provided", () => {
    const result = createShareableLink({ code: null });
    expect(result).toBe("https://marimo.app/");
  });

  it("should return a URL with the provided base URL when no code is provided", () => {
    const result = createShareableLink({
      code: null,
      baseUrl: "https://test.com",
    });
    expect(result).toBe("https://test.com/");
  });

  it("should return a URL with the compressed code in the hash when code is provided", () => {
    const code = 'console.log("Hello, World!")';
    const compressed = compressToEncodedURIComponent(code);
    const result = createShareableLink({ code });
    expect(result).toBe(`https://marimo.app/#code/${compressed}`);
  });

  it("should return a URL with the compressed code in the hash and the provided base URL when code is provided", () => {
    const code = 'console.log("Hello, World!")';
    const baseUrl = "https://test.com/";
    const compressed = compressToEncodedURIComponent(code);
    const result = createShareableLink({ code, baseUrl });
    expect(result).toBe(`${baseUrl}#code/${compressed}`);
  });
});
