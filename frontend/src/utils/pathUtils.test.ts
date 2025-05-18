/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect } from "vitest";
import { getProtocolAndParentDirectories } from "./pathUtils";

describe("getProtocolAndParentDirectories", () => {
  it("should extract protocol and list parent directories correctly", () => {
    const path = "http://example.com/folder/subfolder/";
    const delimiter = "/";
    const initialPath = "http://example.com/folder";
    const restrictNavigation = true;

    const { protocol, parentDirectories } = getProtocolAndParentDirectories(
      path,
      delimiter,
      initialPath,
      restrictNavigation,
    );

    expect(protocol).toBe("http://");
    expect(parentDirectories).toEqual([
      "http://example.com/folder/subfolder",
      "http://example.com/folder",
    ]);
  });

  it("should handle Google Cloud Storage paths", () => {
    const path = "gs://bucket/folder/subfolder/";
    const delimiter = "/";
    const initialPath = "gs://bucket/folder";
    const restrictNavigation = true;

    const { protocol, parentDirectories } = getProtocolAndParentDirectories(
      path,
      delimiter,
      initialPath,
      restrictNavigation,
    );

    expect(protocol).toBe("gs://");
    expect(parentDirectories).toEqual([
      "gs://bucket/folder/subfolder",
      "gs://bucket/folder",
    ]);
  });

  it("should handle S3 paths", () => {
    const path = "s3://bucket/folder/subfolder/";
    const delimiter = "/";
    const initialPath = "s3://bucket/folder";
    const restrictNavigation = true;

    const { protocol, parentDirectories } = getProtocolAndParentDirectories(
      path,
      delimiter,
      initialPath,
      restrictNavigation,
    );

    expect(protocol).toBe("s3://");
    expect(parentDirectories).toEqual([
      "s3://bucket/folder/subfolder",
      "s3://bucket/folder",
    ]);
  });

  it("should handle paths without protocol", () => {
    const path = "/folder/subfolder/";
    const delimiter = "/";
    const initialPath = "/folder";
    const restrictNavigation = false;

    const { protocol, parentDirectories } = getProtocolAndParentDirectories(
      path,
      delimiter,
      initialPath,
      restrictNavigation,
    );

    expect(protocol).toBe("/");
    expect(parentDirectories).toEqual(["/folder/subfolder", "/folder", "/"]);
  });
  it("should handle Windows paths", () => {
    const path = "C:\\folder\\subfolder\\";
    const delimiter = "\\";
    const initialPath = "C:\\folder";
    const restrictNavigation = false;

    const { protocol, parentDirectories } = getProtocolAndParentDirectories(
      path,
      delimiter,
      initialPath,
      restrictNavigation,
    );

    expect(protocol).toBe("C:\\");
    expect(parentDirectories).toEqual([
      "C:\\folder\\subfolder",
      "C:\\folder",
      "C:\\",
    ]);
  });
});
