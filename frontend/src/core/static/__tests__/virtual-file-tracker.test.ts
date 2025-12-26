/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import type { CellId } from "@/core/cells/ids";
import type { OutputMessage } from "@/core/kernel/messages";
import { findVirtualFiles, VirtualFileTracker } from "../virtual-file-tracker";

describe("findVirtualFiles", () => {
  it("should return a set containing all virtual file paths in a string", () => {
    const input =
      "Some text /@file/test-file.js more text /@file/another-file.txt end";
    const expected = new Set([
      "/@file/test-file.js",
      "/@file/another-file.txt",
    ]);
    const result = findVirtualFiles(input);
    expect(result).toEqual(expected);
  });

  it("should return an empty set if no virtual file paths are present", () => {
    const input = "Some text without virtual file paths";
    const expected = new Set();
    const result = findVirtualFiles(input);
    expect(result).toEqual(expected);
  });

  it("should handle non-string inputs by converting them to JSON strings", () => {
    const input = { key: "value", path: "/@file/json-file.json" };
    const expected = new Set(["/@file/json-file.json"]);
    const result = findVirtualFiles(input);
    expect(result).toEqual(expected);
  });

  it("should return an empty set if the input is an empty string", () => {
    const input = "";
    const expected = new Set();
    const result = findVirtualFiles(input);
    expect(result).toEqual(expected);
  });

  it("should return an empty set if the input is null or undefined", () => {
    expect(findVirtualFiles(null)).toEqual(new Set());
    expect(findVirtualFiles(undefined)).toEqual(new Set());
  });

  it("should correctly identify virtual files with complex extensions", () => {
    const input = "File with complex extension /@file/complex-file.min.js";
    const expected = new Set(["/@file/complex-file.min.js"]);
    const result = findVirtualFiles(input);
    expect(result).toEqual(expected);
  });

  it("should not include non-virtual file paths", () => {
    const input =
      "Regular file path /some/regular/file.txt and virtual file /@file/virtual-file.md";
    const expected = new Set(["/@file/virtual-file.md"]);
    const result = findVirtualFiles(input);
    expect(result).toEqual(expected);
  });

  it("should match virtual files with HTML entity endings", () => {
    const input = '"/@file/938947-3587525-4XcHZISt.csv&quot"';
    const expected = new Set(["/@file/938947-3587525-4XcHZISt.csv"]);
    const result = findVirtualFiles(input);
    expect(result).toEqual(expected);
  });

  it("should not match virtual files with mismatched quotes", () => {
    const input = "'/@file/938947-3587525-4XcHZISt.csv\"'";
    const expected = new Set(["/@file/938947-3587525-4XcHZISt.csv"]);
    const result = findVirtualFiles(input);
    expect(result).toEqual(expected);
  });

  it("should match virtual files followed by quotes", () => {
    const input = '/@file/test-file.csv"';
    const expected = new Set(["/@file/test-file.csv"]);
    const result = findVirtualFiles(input);
    expect(result).toEqual(expected);
  });

  it("should match valid virtual files even when surrounded by proper quotes", () => {
    const input = '"/@file/test-file.csv"';
    const expected = new Set(["/@file/test-file.csv"]);
    const result = findVirtualFiles(input);
    expect(result).toEqual(expected);
  });

  it("should extremely long greedy matching", () => {
    const input = `/@file/test-file.csv&quot;,&quot;format&quot;:{&quot;type&quot;:&quot;csv&quot;}},&quot;mark&quot;:{&quot;type&quot;:&quot;circle&quot;,&quot;size&quot;:4},&quot;encoding&quot;:{&quot;color&quot;:{&quot;field&quot;:&quot;digit&quot;,&quot;type&quot;:&quot;nominal&quot;},&quot;x&quot;:{&quot;field&quot;:&quot;x&quot;,&quot;scale&quot;:{&quot;domain&quot;:[-2.5,2.5]},&quot;type&quot;:&quot;quantitative&quot;},&quot;y&quot;:{&quot;field&quot;:&quot;y&quot;,&quot;scale&quot;:{&quot;domain&quot;:[-2.5,2.5. Error: [Errno 63] File name too long: '/3587525-4XcHZISt.csv&quot;,&quot;format&quot;:{&quot;type&quot;:&quot;csv&quot;}},&quot;mark&quot;:{&quot;type&quot;:&quot;circle&quot;,&quot;size&quot;:4},&quot;encoding&quot;:{&quot;color&quot;:{&quot;field&quot;:&quot;digit&quot;,&quot;type&quot;:&quot;nominal&quot;},&quot;x&quot;:{&quot;field&quot;:&quot;x&quot;,&quot;scale&quot;:{&quot;domain&quot;:[-2.5,2.5]},&quot;type&quot;:&quot;quantitative&quot;},&quot;y&quot;:{&quot;field&quot;:&quot;y&quot;,&quot;scale&quot;:{&quot;domain&quot;:[-2.5,2.5'`;
    const expected = new Set(["/@file/test-file.csv"]);
    const result = findVirtualFiles(input);
    expect(result).toEqual(expected);
  });

  it("should not match virtual files with quotes in the filename", () => {
    const input = '/@file/file".csv';
    const expected = new Set();
    const result = findVirtualFiles(input);
    expect(result).toEqual(expected);
  });
});

describe("VirtualFileTracker", () => {
  it("should track virtual files, append, clear", () => {
    const tracker = VirtualFileTracker.INSTANCE;
    const cellId = "test-cell-id" as CellId;
    tracker.track({
      cell_id: cellId,
      output: {
        mimetype: "text/html",
        data: "Some text /@file/test-file.js more text",
      } as OutputMessage,
    });
    expect(tracker.virtualFiles.get(cellId)).toEqual(
      new Set(["/@file/test-file.js"]),
    );

    // can append
    tracker.track({
      cell_id: cellId,
      output: {
        mimetype: "text/html",
        data: "Some text /@file/another-file.txt more text",
      } as OutputMessage,
    });
    expect(tracker.virtualFiles.get(cellId)).toEqual(
      new Set(["/@file/test-file.js", "/@file/another-file.txt"]),
    );

    // can clear
    tracker.removeForCellId(cellId);
    expect(tracker.virtualFiles.get(cellId)).toEqual(undefined);
  });
});
