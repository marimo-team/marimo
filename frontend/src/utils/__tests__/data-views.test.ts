/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect } from "vitest";
import { updateBufferPaths, base64ToDataView } from "../data-views";

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
});

describe("base64ToDataView", () => {
  it("should convert a base64 string to a DataView", () => {
    const input = "Hello";
    const result = base64ToDataView(input);

    expect(result).toBeInstanceOf(DataView);
    expect(result.byteLength).toBe(5);
    expect(result.getUint8(0)).toBe(72); // 'H'
    expect(result.getUint8(1)).toBe(101); // 'e'
    expect(result.getUint8(2)).toBe(108); // 'l'
    expect(result.getUint8(3)).toBe(108); // 'l'
    expect(result.getUint8(4)).toBe(111); // 'o'
  });

  it("should handle empty string", () => {
    const input = "";
    const result = base64ToDataView(input);

    expect(result).toBeInstanceOf(DataView);
    expect(result.byteLength).toBe(0);
  });
});
