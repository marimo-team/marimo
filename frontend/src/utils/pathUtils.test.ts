/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import {
  fileSplit,
  getProtocolAndParentDirectories,
  makeDuplicateName,
  resolvePaths,
  toAbsolutePath,
} from "./pathUtils";

describe("getProtocolAndParentDirectories", () => {
  it("should extract protocol and list parent directories correctly", () => {
    const path = "http://example.com/folder/subfolder/";
    const delimiter = "/";
    const initialPath = "http://example.com/folder";
    const restrictNavigation = true;

    const { protocol, parentDirectories } = getProtocolAndParentDirectories({
      path,
      delimiter,
      initialPath,
      restrictNavigation,
    });

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

    const { protocol, parentDirectories } = getProtocolAndParentDirectories({
      path,
      delimiter,
      initialPath,
      restrictNavigation,
    });

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

    const { protocol, parentDirectories } = getProtocolAndParentDirectories({
      path,
      delimiter,
      initialPath,
      restrictNavigation,
    });

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

    const { protocol, parentDirectories } = getProtocolAndParentDirectories({
      path,
      delimiter,
      initialPath,
      restrictNavigation,
    });

    expect(protocol).toBe("/");
    expect(parentDirectories).toEqual(["/folder/subfolder", "/folder", "/"]);
  });
  it("should handle Windows paths", () => {
    const path = "C:\\folder\\subfolder\\";
    const delimiter = "\\";
    const initialPath = "C:\\folder";
    const restrictNavigation = false;

    const { protocol, parentDirectories } = getProtocolAndParentDirectories({
      path,
      delimiter,
      initialPath,
      restrictNavigation,
    });

    expect(protocol).toBe("C:\\");
    expect(parentDirectories).toEqual([
      "C:\\folder\\subfolder",
      "C:\\folder",
      "C:\\",
    ]);
  });
});

describe("fileSplit", () => {
  it("should split a path into a name and extension", () => {
    expect(fileSplit("path/to/file.txt")).toEqual(["path/to/file", ".txt"]);
    expect(fileSplit("path/to/file")).toEqual(["path/to/file", ""]);
    expect(fileSplit("path/to/file.txt.md")).toEqual([
      "path/to/file.txt",
      ".md",
    ]);
  });
});

describe("makeDuplicateName", () => {
  it("appends _copy before the extension", () => {
    expect(makeDuplicateName("notebook.py")).toBe("notebook_copy.py");
    expect(makeDuplicateName("foo.tar.gz")).toBe("foo.tar_copy.gz");
  });

  it("appends _copy for extensionless names", () => {
    expect(makeDuplicateName("README")).toBe("README_copy");
  });
});

describe("toAbsolutePath", () => {
  it("joins relative paths against the root", () => {
    expect(toAbsolutePath("notebooks/a.py", "/workspaces/marimo")).toBe(
      "/workspaces/marimo/notebooks/a.py",
    );
  });

  it("returns absolute POSIX paths unchanged", () => {
    expect(toAbsolutePath("/abs/a.py", "/workspaces/marimo")).toBe("/abs/a.py");
  });

  it("returns absolute Windows paths unchanged", () => {
    expect(toAbsolutePath("C:\\Users\\x\\a.py", "C:\\Users\\marimo")).toBe(
      "C:\\Users\\x\\a.py",
    );
  });

  it("joins relative paths using the Windows delimiter", () => {
    expect(toAbsolutePath("a.py", "C:\\Users\\marimo")).toBe(
      "C:\\Users\\marimo\\a.py",
    );
  });
});

describe("resolvePaths", () => {
  it("resolves relative paths against the root", () => {
    expect(
      resolvePaths({
        path: "notebooks/notebook.py",
        name: "notebook_copy.py",
        root: "/workspaces/marimo",
      }),
    ).toEqual({
      path: "/workspaces/marimo/notebooks/notebook.py",
      newPath: "/workspaces/marimo/notebooks/notebook_copy.py",
    });
  });

  it("keeps absolute source paths untouched", () => {
    expect(
      resolvePaths({
        path: "/abs/path/notebook.py",
        name: "notebook_copy.py",
        root: "/workspaces/marimo",
      }),
    ).toEqual({
      path: "/abs/path/notebook.py",
      newPath: "/abs/path/notebook_copy.py",
    });
  });

  it("handles Windows roots for relative paths", () => {
    expect(
      resolvePaths({
        path: "notebook.py",
        name: "notebook_copy.py",
        root: "C:\\Users\\marimo",
      }),
    ).toEqual({
      path: "C:\\Users\\marimo\\notebook.py",
      newPath: "C:\\Users\\marimo\\notebook_copy.py",
    });
  });

  it("handles Windows absolute source paths", () => {
    // The tricky case: `path` is an absolute Windows path with a drive letter,
    // so it must be detected by `Paths.isAbsolute` AND the deliminator must be
    // picked up from the root so the join uses backslashes.
    expect(
      resolvePaths({
        path: "C:\\Users\\marimo\\folder\\notebook.py",
        name: "notebook_copy.py",
        root: "C:\\Users\\marimo",
      }),
    ).toEqual({
      path: "C:\\Users\\marimo\\folder\\notebook.py",
      newPath: "C:\\Users\\marimo\\folder\\notebook_copy.py",
    });
  });

  it("keeps the file in its current directory when renaming", () => {
    expect(
      resolvePaths({
        path: "/root/a/b/file.py",
        name: "renamed.py",
        root: "/root",
      }),
    ).toEqual({
      path: "/root/a/b/file.py",
      newPath: "/root/a/b/renamed.py",
    });
  });

  it("handles an empty root with an absolute POSIX path", () => {
    // Callers that already hold absolute paths pass `root: ""`. In that case
    // the delimiter must be inferred from the path itself, not from `""` (which
    // would otherwise default to Windows backslashes).
    expect(
      resolvePaths({
        path: "/abs/path/file.py",
        name: "renamed.py",
        root: "",
      }),
    ).toEqual({
      path: "/abs/path/file.py",
      newPath: "/abs/path/renamed.py",
    });
  });

  it("handles an empty root with an absolute Windows path", () => {
    expect(
      resolvePaths({
        path: "C:\\Users\\marimo\\file.py",
        name: "renamed.py",
        root: "",
      }),
    ).toEqual({
      path: "C:\\Users\\marimo\\file.py",
      newPath: "C:\\Users\\marimo\\renamed.py",
    });
  });
});
