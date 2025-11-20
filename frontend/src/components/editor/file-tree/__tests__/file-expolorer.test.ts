import { describe, expect, it } from "vitest";
import type { FileInfo } from "@/core/network/types";
import { filterHiddenTree, isDirectoryOrFileHidden } from "../file-explorer";

// Helpers to build FileInfo objects for tests
const file = (name: string, path: string): FileInfo => ({
  id: path,
  name,
  path,
  isDirectory: false,
  isMarimoFile: false,
  children: [],
});

const dir = (
  name: string,
  path: string,
  children: FileInfo[] = [],
): FileInfo => ({
  id: path,
  name,
  path,
  isDirectory: true,
  isMarimoFile: false,
  children,
});

describe("isDirectoryOrFileHidden", () => {
  it("should return true for files starting with dot", () => {
    expect(isDirectoryOrFileHidden(".git")).toBe(true);
    expect(isDirectoryOrFileHidden(".env")).toBe(true);
    expect(isDirectoryOrFileHidden(".gitignore")).toBe(true);
  });

  it("should return false for normal files", () => {
    expect(isDirectoryOrFileHidden("README.md")).toBe(false);
    expect(isDirectoryOrFileHidden("package.json")).toBe(false);
    expect(isDirectoryOrFileHidden("index.ts")).toBe(false);
  });

  it("should return false for files with dots in the middle", () => {
    expect(isDirectoryOrFileHidden("file.test.ts")).toBe(false);
    expect(isDirectoryOrFileHidden("my.config.js")).toBe(false);
  });
});

describe("filterHiddenTree", () => {
  it("should return all items when showHidden is true", () => {
    const list: FileInfo[] = [
      dir(".git", "/.git", []),
      file("README.md", "/README.md"),
      file(".env", "/.env"),
    ];

    const result = filterHiddenTree(list, true);

    expect(result).toBe(list); // should be the exact same reference
    expect(result).toHaveLength(3);
  });

  it("should filter out hidden files when showHidden is false", () => {
    const list: FileInfo[] = [
      dir(".git", "/.git"),
      file("README.md", "/README.md"),
      file(".env", "/.env"),
      file("package.json", "/package.json"),
    ];

    const result = filterHiddenTree(list, false);

    expect(result).toHaveLength(2);
    expect(result[0].name).toBe("README.md");
    expect(result[1].name).toBe("package.json");
  });

  it("should filter hidden directories recursively", () => {
    const list: FileInfo[] = [
      dir("src", "/src", [
        file("index.ts", "/src/index.ts"),
        file(".DS_Store", "/src/.DS_Store"),
        file("utils.ts", "/src/utils.ts"),
      ]),
      dir(".git", "/.git", [file("config", "/.git/config")]),
    ];

    const result = filterHiddenTree(list, false);

    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("src");
    expect(result[0].children).toHaveLength(2);
    expect(result[0].children?.[0].name).toBe("index.ts");
    expect(result[0].children?.[1].name).toBe("utils.ts");
  });

  it("should handle nested hidden files", () => {
    const list: FileInfo[] = [
      dir("project", "/project", [
        dir("src", "/project/src", [
          file("index.ts", "/project/src/index.ts"),
          file(".backup", "/project/src/.backup"),
        ]),
        file(".env", "/project/.env"),
      ]),
    ];

    const result = filterHiddenTree(list, false);

    expect(result).toHaveLength(1);
    expect(result[0].children).toHaveLength(1);
    expect(result[0].children?.[0].name).toBe("src");
    expect(result[0].children?.[0].children).toHaveLength(1);
    expect(result[0].children?.[0].children?.[0].name).toBe("index.ts");
  });

  it("should preserve directory structure when no children are filtered", () => {
    const list: FileInfo[] = [
      dir("src", "/src", [
        file("index.ts", "/src/index.ts"),
        file("utils.ts", "/src/utils.ts"),
      ]),
    ];

    const result = filterHiddenTree(list, true);

    // Should return the same reference since nothing changed
    expect(result[0]).toBe(list[0]);
  });

  it("should create new object only when children are filtered", () => {
    const list: FileInfo[] = [
      dir("src", "/src", [
        file("index.ts", "/src/index.ts"),
        file(".hidden", "/src/.hidden"),
      ]),
    ];

    const result = filterHiddenTree(list, false);

    // Should be a new object since children changed
    expect(result[0]).not.toBe(list[0]);
    expect(result[0].children).not.toBe(list[0].children);
  });

  it("should handle empty list", () => {
    const result = filterHiddenTree([], false);
    expect(result).toEqual([]);
  });

  it("should handle empty children arrays", () => {
    const list: FileInfo[] = [dir("empty-dir", "/empty-dir", [])];

    const result = filterHiddenTree(list, false);

    expect(result).toHaveLength(1);
    expect(result[0].children).toEqual([]);
  });

  it("should handle deeply nested structures", () => {
    const list: FileInfo[] = [
      dir("level1", "/level1", [
        dir("level2", "/level1/level2", [
          dir("level3", "/level1/level2/level3", [
            file("file.ts", "/level1/level2/level3/file.ts"),
            file(".hidden", "/level1/level2/level3/.hidden"),
          ]),
        ]),
        file(".ignore", "/level1/.ignore"),
      ]),
    ];

    const result = filterHiddenTree(list, false);

    expect(result[0].children?.[0].children?.[0].children).toHaveLength(1);
    expect(result[0].children?.[0].children?.[0].children?.[0].name).toBe(
      "file.ts",
    );
  });
});
