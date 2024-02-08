/* Copyright 2024 Marimo. All rights reserved. */
import { expect, describe, it } from "vitest";
import { VirtualFileTracker, findVirtualFiles } from "../virtual-file-tracker";
import { CellId } from "@/core/cells/ids";
import { OutputMessage } from "@/core/kernel/messages";

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
