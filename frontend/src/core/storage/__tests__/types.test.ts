/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { storageNamespacePrefix, storagePathKey, storageUrl } from "../types";

describe("storagePathKey", () => {
  it("should join namespace and prefix", () => {
    expect(storagePathKey("ns", "data/")).toBe("ns::data/");
  });

  it("should use empty string for null prefix", () => {
    expect(storagePathKey("ns", null)).toBe("ns::");
  });

  it("should use empty string for undefined prefix", () => {
    expect(storagePathKey("ns", undefined)).toBe("ns::");
  });
});

describe("storageNamespacePrefix", () => {
  it("should append separator", () => {
    expect(storageNamespacePrefix("my_s3")).toBe("my_s3::");
  });
});

describe("storageUrl", () => {
  it("should combine protocol, rootPath, and entryPath", () => {
    expect(storageUrl("s3", "my-bucket", "data/file.csv")).toEqual(
      new URL("s3://my-bucket/data/file.csv"),
    );
  });

  it("should handle empty rootPath", () => {
    expect(storageUrl("s3", "", "marimo-artifacts/file.csv")).toEqual(
      new URL("s3://marimo-artifacts/file.csv"),
    );
  });

  it("should handle rootPath with trailing slash", () => {
    expect(storageUrl("s3", "my-bucket/", "data/file.csv")).toEqual(
      new URL("s3://my-bucket/data/file.csv"),
    );
  });

  it("should handle entryPath with leading slash", () => {
    expect(storageUrl("s3", "my-bucket", "/data/file.csv")).toEqual(
      new URL("s3://my-bucket/data/file.csv"),
    );
  });

  it("should collapse multiple slashes between rootPath and entryPath", () => {
    expect(storageUrl("s3", "my-bucket/", "/data/file.csv")).toEqual(
      new URL("s3://my-bucket/data/file.csv"),
    );
  });

  it("should handle directory paths with trailing slash", () => {
    expect(storageUrl("gcs", "my-bucket", "data/")).toEqual(
      new URL("gcs://my-bucket/data/"),
    );
  });

  it("should handle empty entryPath", () => {
    expect(storageUrl("s3", "my-bucket", "")).toEqual(
      new URL("s3://my-bucket"),
    );
  });

  it("should handle both rootPath and entryPath empty", () => {
    expect(storageUrl("s3", "", "")).toEqual(new URL("s3://"));
  });

  it("should work with file protocol", () => {
    expect(storageUrl("file", "/home/user", "docs/readme.md")).toEqual(
      new URL("file:///home/user/docs/readme.md"),
    );
  });

  it("should work with nested rootPath", () => {
    expect(storageUrl("s3", "bucket/prefix", "sub/file.txt")).toEqual(
      new URL("s3://bucket/prefix/sub/file.txt"),
    );
  });
});
