/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import type { StorageEntry, StoragePathKey } from "@/core/storage/types";
import { storagePathKey } from "@/core/storage/types";
import { exportedForTesting } from "../storage-inspector";

const { filterEntries, remoteSearchPrefix, storageEntryKey } =
  exportedForTesting;

function makeEntry(
  overrides: Partial<StorageEntry> & { path: string },
): StorageEntry {
  return {
    kind: overrides.kind ?? "file",
    lastModified: overrides.lastModified ?? null,
    metadata: overrides.metadata ?? {},
    path: overrides.path,
    size: overrides.size ?? 0,
  };
}

describe("storageEntryKey", () => {
  it("prefers the backend id when present (e.g. Google Drive)", () => {
    const entry = makeEntry({
      path: "Data Resume.pdf",
      metadata: { id: "drive-file-id-123" },
    });
    // Two files can share a path on Drive; the id keeps keys unique.
    expect(storageEntryKey(entry, 0)).toBe("drive-file-id-123");
    expect(storageEntryKey(entry, 4)).toBe("drive-file-id-123");
  });

  it("falls back to path + index when there is no id", () => {
    const entry = makeEntry({ path: "Data Resume.pdf" });
    expect(storageEntryKey(entry, 0)).toBe("Data Resume.pdf::0");
    expect(storageEntryKey(entry, 4)).toBe("Data Resume.pdf::4");
  });

  it("keeps duplicate-path entries unique via the index fallback", () => {
    const entries = [
      makeEntry({ path: "Data Resume.pdf" }),
      makeEntry({ path: "Data Resume.pdf" }),
      makeEntry({ path: "Data Resume.pdf" }),
    ];
    const keys = entries.map((entry, index) => storageEntryKey(entry, index));
    expect(new Set(keys).size).toBe(entries.length);
  });

  it("ignores a non-string or empty id", () => {
    expect(
      storageEntryKey(makeEntry({ path: "a.pdf", metadata: { id: "" } }), 2),
    ).toBe("a.pdf::2");
    expect(
      storageEntryKey(makeEntry({ path: "a.pdf", metadata: { id: 5 } }), 2),
    ).toBe("a.pdf::2");
  });
});

describe("storage inspector search", () => {
  describe("remoteSearchPrefix", () => {
    it("returns the parent directory of the query so backends can list it", () => {
      // Object stores match prefixes on path segments, so we list the parent
      // directory and filter the rest client-side.
      expect(remoteSearchPrefix("folder/x")).toBe("folder/");
      expect(remoteSearchPrefix("nested/folder/x")).toBe("nested/folder/");
    });

    it("preserves trailing slashes when the user explicitly typed one", () => {
      expect(remoteSearchPrefix("folder/x/")).toBe("folder/x/");
      expect(remoteSearchPrefix("nested/folder/x/")).toBe("nested/folder/x/");
      expect(remoteSearchPrefix("/")).toBe("/");
    });

    it("returns an empty string for queries without a directory component", () => {
      // Without a slash there is nothing useful to send to the backend; rely on
      // local filtering instead.
      expect(remoteSearchPrefix("x")).toBe("");
      expect(remoteSearchPrefix("report")).toBe("");
    });

    it("trims leading/trailing whitespace before computing the prefix", () => {
      expect(remoteSearchPrefix("  nested/folder/x  ")).toBe("nested/folder/");
      expect(remoteSearchPrefix("  ")).toBe("");
    });
  });

  describe("filterEntries", () => {
    it("matches loaded entries by basename, extension, and full path", () => {
      const entries = [
        makeEntry({ path: "data/report.csv" }),
        makeEntry({ path: "logs/readme.md" }),
      ];

      expect(
        filterEntries({
          entries,
          namespace: "store",
          searchValue: ".csv",
          entriesByPath: new Map(),
        }),
      ).toEqual([entries[0]]);
      expect(
        filterEntries({
          entries,
          namespace: "store",
          searchValue: "data/report",
          entriesByPath: new Map(),
        }),
      ).toEqual([entries[0]]);
      expect(
        filterEntries({
          entries,
          namespace: "store",
          searchValue: "readme",
          entriesByPath: new Map(),
        }),
      ).toEqual([entries[1]]);
    });

    it("returns the original entries when search is cleared", () => {
      const entries = [
        makeEntry({ path: "data/report.csv" }),
        makeEntry({ path: "logs/readme.md" }),
      ];

      expect(
        filterEntries({
          entries,
          namespace: "store",
          searchValue: "",
          entriesByPath: new Map(),
        }),
      ).toBe(entries);
    });

    it("keeps directories whose loaded descendants match a path query", () => {
      const directory = makeEntry({ path: "data", kind: "directory" });
      const child = makeEntry({ path: "data/report.csv" });
      const entriesByPath = new Map<StoragePathKey, StorageEntry[]>([
        [storagePathKey("store", "data/"), [child]],
      ]);

      expect(
        filterEntries({
          entries: [directory],
          namespace: "store",
          searchValue: "data/report",
          entriesByPath,
        }),
      ).toEqual([directory]);
    });

    it("matches partial path queries against loaded sibling files (folder/x -> folder/xsomething)", () => {
      // Regression test for the obstore path-segment prefix bug: typing
      // "folder/x" should surface "folder/xsomething" once the folder has
      // been listed locally.
      const folder = makeEntry({ path: "folder/", kind: "directory" });
      const matching = makeEntry({ path: "folder/xsomething" });
      const matchingAlt = makeEntry({ path: "folder/xanother" });
      const other = makeEntry({ path: "folder/something" });
      const entriesByPath = new Map<StoragePathKey, StorageEntry[]>([
        [storagePathKey("store", "folder/"), [other, matchingAlt, matching]],
      ]);

      expect(
        filterEntries({
          entries: [folder],
          namespace: "store",
          searchValue: "folder/x",
          entriesByPath,
        }),
      ).toEqual([folder]);

      // Same query, but applied directly to the loaded folder contents (as
      // happens for the "remote results" fallback) should drop non-matches.
      expect(
        filterEntries({
          entries: [other, matchingAlt, matching],
          namespace: "store",
          searchValue: "folder/x",
          entriesByPath,
        }),
      ).toEqual([matchingAlt, matching]);
    });
  });
});
