/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect } from "vitest";
import { updateBufferPaths, byteStringToDataView } from "../data-views";
import type { ByteString, Base64String } from "../json/base64";

describe("updateBufferPaths", () => {
  it("should return the original object if bufferPaths is null", () => {
    const input = { a: 1, b: 2 };
    const result = updateBufferPaths(input, null);
    expect(result).toEqual(input);
  });

  it("should update buffer paths correctly", () => {
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
    const result = updateBufferPaths(input, bufferPaths);

    expect(result.a).toBe(1);
    expect(result.b.c).toBeInstanceOf(DataView);
    expect(result.b.d).toBeInstanceOf(DataView);
  });

  it("should handle non-existent paths", () => {
    const input = { a: 1 };
    const bufferPaths = [["b", "c"]];
    const result = updateBufferPaths(input, bufferPaths);

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
    const buffers: Base64String[] = [
      "SGVsbG8=" as Base64String,
      "V29ybGQ=" as Base64String,
    ]; // Base64 encoded "Hello" and "World"
    const result = updateBufferPaths(input, bufferPaths, buffers);

    expect(result.a).toBe(1);
    const cView = result.b.c as unknown as DataView;
    const dView = result.b.d as unknown as DataView;
    expect(cView).toBeInstanceOf(DataView);
    expect(dView).toBeInstanceOf(DataView);
    expect(cView.byteLength).toBe(5);
    expect(dView.byteLength).toBe(5);
  });

  it("should throw error when buffers and paths length mismatch", () => {
    const input = { a: 1 };
    const bufferPaths = [
      ["b", "c"],
      ["b", "d"],
    ];
    const buffers: Base64String[] = ["SGVsbG8=" as Base64String]; // Only one buffer for two paths

    expect(() => updateBufferPaths(input, bufferPaths, buffers)).toThrow(
      "Buffers and buffer paths not the same length",
    );
  });

  it("should handle empty buffers array", () => {
    const input = { a: 1 };
    const bufferPaths = [["b", "c"]];
    const buffers: Base64String[] = [];

    expect(() => updateBufferPaths(input, bufferPaths, buffers)).toThrow(
      "Buffers and buffer paths not the same length",
    );
  });
});

describe("byteStringToDataView", () => {
  it("should convert a base64 string to a DataView", () => {
    const input = "Hello" as ByteString;
    const result = byteStringToDataView(input);

    expect(result).toBeInstanceOf(DataView);
    expect(result.byteLength).toBe(5);
    expect(result.getUint8(0)).toBe(72); // 'H'
    expect(result.getUint8(1)).toBe(101); // 'e'
    expect(result.getUint8(2)).toBe(108); // 'l'
    expect(result.getUint8(3)).toBe(108); // 'l'
    expect(result.getUint8(4)).toBe(111); // 'o'
  });

  it("should handle empty string", () => {
    const input = "" as ByteString;
    const result = byteStringToDataView(input);

    expect(result).toBeInstanceOf(DataView);
    expect(result.byteLength).toBe(0);
  });
});
