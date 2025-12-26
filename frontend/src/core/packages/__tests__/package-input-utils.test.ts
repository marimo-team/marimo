/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { stripPackageManagerPrefix } from "../package-input-utils";

describe("stripPackageManagerPrefix", () => {
  it("should remove 'pip install' prefix", () => {
    expect(stripPackageManagerPrefix("pip install httpx")).toBe("httpx");
    expect(stripPackageManagerPrefix("pip install httpx requests")).toBe(
      "httpx requests",
    );
  });

  it("should remove 'pip3 install' prefix", () => {
    expect(stripPackageManagerPrefix("pip3 install pandas")).toBe("pandas");
  });

  it("should remove 'uv add' prefix", () => {
    expect(stripPackageManagerPrefix("uv add numpy")).toBe("numpy");
    expect(stripPackageManagerPrefix("uv add pandas numpy")).toBe(
      "pandas numpy",
    );
  });

  it("should remove 'uv pip install' prefix", () => {
    expect(stripPackageManagerPrefix("uv pip install scipy")).toBe("scipy");
  });

  it("should remove 'poetry add' prefix", () => {
    expect(stripPackageManagerPrefix("poetry add flask")).toBe("flask");
  });

  it("should remove 'conda install' prefix", () => {
    expect(stripPackageManagerPrefix("conda install matplotlib")).toBe(
      "matplotlib",
    );
  });

  it("should remove 'pipenv install' prefix", () => {
    expect(stripPackageManagerPrefix("pipenv install django")).toBe("django");
  });

  it("should be case insensitive", () => {
    expect(stripPackageManagerPrefix("PIP INSTALL httpx")).toBe("httpx");
    expect(stripPackageManagerPrefix("Pip Install requests")).toBe("requests");
    expect(stripPackageManagerPrefix("UV ADD numpy")).toBe("numpy");
  });

  it("should handle extra whitespace", () => {
    expect(stripPackageManagerPrefix("  pip install   httpx  ")).toBe("httpx");
    expect(stripPackageManagerPrefix("uv add    pandas   ")).toBe("pandas");
  });

  it("should return input unchanged if no prefix matches", () => {
    expect(stripPackageManagerPrefix("httpx")).toBe("httpx");
    expect(stripPackageManagerPrefix("pandas numpy")).toBe("pandas numpy");
    expect(stripPackageManagerPrefix("httpx==0.27.0")).toBe("httpx==0.27.0");
  });

  it("should handle package specifications with versions", () => {
    expect(stripPackageManagerPrefix("pip install httpx==0.27.0")).toBe(
      "httpx==0.27.0",
    );
    expect(stripPackageManagerPrefix("uv add pandas>=2.0.0")).toBe(
      "pandas>=2.0.0",
    );
  });

  it("should handle git URLs", () => {
    expect(
      stripPackageManagerPrefix(
        "pip install git+https://github.com/encode/httpx",
      ),
    ).toBe("git+https://github.com/encode/httpx");
  });

  it("should handle multiple packages", () => {
    expect(stripPackageManagerPrefix("pip install httpx requests pandas")).toBe(
      "httpx requests pandas",
    );
  });

  it("should only remove the first matching prefix", () => {
    // Edge case: input contains prefix-like text multiple times
    expect(stripPackageManagerPrefix("pip install pip install httpx")).toBe(
      "pip install httpx",
    );
  });

  it("should handle empty string", () => {
    expect(stripPackageManagerPrefix("")).toBe("");
    expect(stripPackageManagerPrefix("   ")).toBe("");
  });
});
