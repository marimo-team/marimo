/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import type { StorageEntry } from "@/core/storage/types";
import { exportedForTesting } from "../storage-inspector";

const { storageEntryKey } = exportedForTesting;

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
