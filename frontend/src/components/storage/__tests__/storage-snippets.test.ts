/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import {
  STORAGE_SNIPPETS,
  type StorageSnippetContext,
} from "../storage-snippets";

const readSnippet = STORAGE_SNIPPETS.find((s) => s.id === "read-file")!;
const downloadSnippet = STORAGE_SNIPPETS.find((s) => s.id === "download-file")!;

function makeCtx(
  overrides: Partial<StorageSnippetContext> = {},
): StorageSnippetContext {
  return {
    variableName: "store",
    protocol: "s3",
    entry: {
      path: "data/file.csv",
      kind: "object",
      size: 1024,
      lastModified: null,
    },
    backendType: "obstore",
    ...overrides,
  };
}

describe("read-file snippet", () => {
  it("obstore backend", () => {
    expect(readSnippet.getCode(makeCtx())).toMatchInlineSnapshot(`
      "_data = store.get("data/file.csv").bytes()
      _data"
    `);
  });

  it("fsspec backend", () => {
    expect(
      readSnippet.getCode(
        makeCtx({ backendType: "fsspec", variableName: "fs" }),
      ),
    ).toMatchInlineSnapshot(`
      "_data = fs.cat_file("data/file.csv")
      _data"
    `);
  });

  it("returns null for directories", () => {
    expect(
      readSnippet.getCode(
        makeCtx({
          entry: {
            path: "data/",
            kind: "directory",
            size: 0,
            lastModified: null,
          },
        }),
      ),
    ).toBeNull();
  });

  it("escapes double quotes in paths", () => {
    expect(
      readSnippet.getCode(
        makeCtx({
          entry: {
            path: 'data/"file".csv',
            kind: "object",
            size: 100,
            lastModified: null,
          },
        }),
      ),
    ).toMatchInlineSnapshot(`
      "_data = store.get("data/\\"file\\".csv").bytes()
      _data"
    `);
  });

  it("escapes backslashes in paths", () => {
    expect(
      readSnippet.getCode(
        makeCtx({
          entry: {
            path: "data\\file.csv",
            kind: "object",
            size: 100,
            lastModified: null,
          },
        }),
      ),
    ).toMatchInlineSnapshot(`
      "_data = store.get("data\\\\file.csv").bytes()
      _data"
    `);
  });

  it("escapes newlines and tabs in paths", () => {
    expect(
      readSnippet.getCode(
        makeCtx({
          entry: {
            path: "data/file\nname\there.csv",
            kind: "object",
            size: 100,
            lastModified: null,
          },
        }),
      ),
    ).toMatchInlineSnapshot(`
      "_data = store.get("data/file\\nname\\there.csv").bytes()
      _data"
    `);
  });

  it("escapes control characters in paths", () => {
    expect(
      readSnippet.getCode(
        makeCtx({
          entry: {
            path: "data/\u0000\u001F.csv",
            kind: "object",
            size: 100,
            lastModified: null,
          },
        }),
      ),
    ).toMatchInlineSnapshot(`
      "_data = store.get("data/\\u0000\\u001f.csv").bytes()
      _data"
    `);
  });
});

describe("download-file snippet", () => {
  it("obstore s3 backend", () => {
    expect(downloadSnippet.getCode(makeCtx())).toMatchInlineSnapshot(`
      "from datetime import timedelta
      from obstore import sign

      signed_url = sign(
          store, "GET", "data/file.csv",
          expires_in=timedelta(hours=1),
      )
      signed_url"
    `);
  });

  it("obstore gcs backend", () => {
    expect(downloadSnippet.getCode(makeCtx({ protocol: "gcs" })))
      .toMatchInlineSnapshot(`
      "from datetime import timedelta
      from obstore import sign

      signed_url = sign(
          store, "GET", "data/file.csv",
          expires_in=timedelta(hours=1),
      )
      signed_url"
    `);
  });

  it("obstore cloudflare backend", () => {
    expect(downloadSnippet.getCode(makeCtx({ protocol: "cloudflare" })))
      .toMatchInlineSnapshot(`
      "from datetime import timedelta
      from obstore import sign

      signed_url = sign(
          store, "GET", "data/file.csv",
          expires_in=timedelta(hours=1),
      )
      signed_url"
    `);
  });

  it("returns null for http obstore (not signable)", () => {
    expect(downloadSnippet.getCode(makeCtx({ protocol: "http" }))).toBeNull();
  });

  it("returns null for file obstore (not signable)", () => {
    expect(downloadSnippet.getCode(makeCtx({ protocol: "file" }))).toBeNull();
  });

  it("returns null for in-memory obstore (not signable)", () => {
    expect(
      downloadSnippet.getCode(makeCtx({ protocol: "in-memory" })),
    ).toBeNull();
  });

  it("fsspec backend", () => {
    expect(
      downloadSnippet.getCode(
        makeCtx({ backendType: "fsspec", variableName: "fs" }),
      ),
    ).toMatchInlineSnapshot(`"fs.get("data/file.csv", "file.csv")"`);
  });

  it("fsspec backend with nested path", () => {
    expect(
      downloadSnippet.getCode(
        makeCtx({
          backendType: "fsspec",
          variableName: "fs",
          entry: {
            path: "nested/dir/report.parquet",
            kind: "file",
            size: 500,
            lastModified: null,
          },
        }),
      ),
    ).toMatchInlineSnapshot(
      `"fs.get("nested/dir/report.parquet", "report.parquet")"`,
    );
  });

  it("returns null for directories", () => {
    expect(
      downloadSnippet.getCode(
        makeCtx({
          entry: {
            path: "data/",
            kind: "directory",
            size: 0,
            lastModified: null,
          },
        }),
      ),
    ).toBeNull();
  });
});

describe("all snippets return null for directories", () => {
  for (const snippet of STORAGE_SNIPPETS) {
    it(`${snippet.id} returns null for directory entries`, () => {
      expect(
        snippet.getCode(
          makeCtx({
            entry: {
              path: "some-dir/",
              kind: "directory",
              size: 0,
              lastModified: null,
            },
          }),
        ),
      ).toBeNull();
    });
  }
});
