/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { updateBufferPaths } from "../data-views";

describe("updateBufferPaths", () => {
  it("should return the original object if bufferPaths.length === 0", () => {
    const input = { a: 1, b: 2 };
    const result = updateBufferPaths(input, [], []);
    expect(result).toEqual(input);
  });

  it("should update buffer paths with provided buffers", () => {
    const input = {
      a: 1,
      b: {
        c: "Hello",
        d: "World",
      },
    };
    const bufferPaths = [
      ["b", "c"],
      ["b", "d"],
    ];
    const buffers = [
      new TextEncoder().encode("Hello"),
      new TextEncoder().encode("World"),
    ].map((b) => new DataView(b.buffer));
    const result = updateBufferPaths(input, bufferPaths, buffers);
    expect(result).toMatchInlineSnapshot();
  });

  it("should throw error when buffers and paths length mismatch", () => {
    const input = { a: 1 };
    const bufferPaths = [
      ["b", "c"],
      ["b", "d"],
    ];
    const buffers = [new DataView(new ArrayBuffer())]; // Only one buffer for two paths

    expect(() => updateBufferPaths(input, bufferPaths, buffers)).toThrow(
      "Buffers and buffer paths not the same length",
    );
  });

  it("should handle empty buffers array", () => {
    const input = { a: 1 };
    const bufferPaths = [["b", "c"]];
    const buffers: DataView[] = [];

    expect(() => updateBufferPaths(input, bufferPaths, buffers)).toThrow(
      "Buffers and buffer paths not the same length",
    );
  });
});
