/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, test } from "vitest";
import {
  type Base64String,
  base64ToDataURL,
  base64ToDataView,
  base64ToUint8Array,
  type DataURLString,
  dataViewToBase64,
  deserializeJson,
  extractBase64FromDataURL,
  isDataURLString,
  type JsonString,
  uint8ArrayToBase64,
} from "../base64";

describe("base64", () => {
  describe("deserializeJson", () => {
    test("deserializes JSON string to object", () => {
      const json = '{"name":"marimo","type":"notebook"}' as JsonString<{
        name: string;
        type: string;
      }>;
      const result = deserializeJson(json);
      expect(result).toEqual({ name: "marimo", type: "notebook" });
    });

    test("deserializes JSON array", () => {
      const json = "[1,2,3]" as JsonString<number[]>;
      const result = deserializeJson(json);
      expect(result).toEqual([1, 2, 3]);
    });
  });

  describe("base64ToDataURL", () => {
    test("creates proper data URL with mime type", () => {
      const base64 = "SGVsbG8=" as Base64String;
      const result = base64ToDataURL(base64, "text/plain");
      expect(result).toBe("data:text/plain;base64,SGVsbG8=");
    });

    test("handles image mime types", () => {
      const base64 = "iVBORw0KGgo=" as Base64String;
      const result = base64ToDataURL(base64, "image/png");
      expect(result).toBe("data:image/png;base64,iVBORw0KGgo=");
    });
  });

  describe("isDataURLString", () => {
    test.each([
      ["data:text/plain;base64,SGVsbG8=", true],
      ["data:image/png;base64,iVBORw0KGgoAAAANSUhEUgA", true],
      ["not-a-data-url", false],
      ["base64,SGVsbG8=", false],
      ["data:text/plain,hello", false],
      ["data:text/plain;charset=utf-8,hello", false],
    ])("isDataURLString(%s) returns %s", (input, expected) => {
      expect(isDataURLString(input)).toBe(expected);
    });
  });

  describe("extractBase64FromDataURL", () => {
    test.each([
      ["data:text/plain;base64,SGVsbG8=", "SGVsbG8="],
      [
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgA",
        "iVBORw0KGgoAAAANSUhEUgA",
      ],
      ["data:application/json;base64,", ""],
      ["data:text/html;charset=utf-8;base64,PGh0bWw+", "PGh0bWw+"],
    ])("extracts base64 from %s", (dataUrl, expected) => {
      expect(extractBase64FromDataURL(dataUrl as DataURLString)).toBe(expected);
    });
  });

  describe("base64ToUint8Array", () => {
    test("converts base64 to Uint8Array", () => {
      const base64 = "QUJD" as Base64String; // "ABC"
      const result = base64ToUint8Array(base64);
      expect(result).toEqual(new Uint8Array([65, 66, 67]));
    });

    test("handles empty base64 string", () => {
      const base64 = "" as Base64String;
      const result = base64ToUint8Array(base64);
      expect(result).toEqual(new Uint8Array([]));
    });
  });

  describe("base64ToDataView", () => {
    test("converts base64 to DataView", () => {
      const base64 = "QUJD" as Base64String; // "ABC"
      const result = base64ToDataView(base64);
      expect(result.byteLength).toBe(3);
      expect(result.getUint8(0)).toBe(65);
      expect(result.getUint8(1)).toBe(66);
      expect(result.getUint8(2)).toBe(67);
    });
  });

  describe("uint8ArrayToBase64", () => {
    test("converts Uint8Array to base64", () => {
      const array = new Uint8Array([65, 66, 67]);
      const result = uint8ArrayToBase64(array);
      expect(result).toBe("QUJD");
    });

    test("handles empty Uint8Array", () => {
      const array = new Uint8Array([]);
      const result = uint8ArrayToBase64(array);
      expect(result).toBe("");
    });
  });

  describe("dataViewToBase64", () => {
    test("should convert a DataView to a base64 string", () => {
      const encoder = new TextEncoder();
      const bytes = encoder.encode("Hello, World!");
      const dataView = new DataView(bytes.buffer);
      const base64 = dataViewToBase64(dataView);

      // Decode and verify
      const decoded = atob(base64);
      expect(decoded).toBe("Hello, World!");
    });

    test("should handle empty DataView", () => {
      const dataView = new DataView(new ArrayBuffer(0));
      const base64 = dataViewToBase64(dataView);
      expect(base64).toBe("");
    });

    test("should handle DataView with offset and length", () => {
      const encoder = new TextEncoder();
      const bytes = encoder.encode("Hello, World!");
      // Create a DataView that only looks at "World!"
      const dataView = new DataView(bytes.buffer, 7, 6);
      const base64 = dataViewToBase64(dataView);

      const decoded = atob(base64);
      expect(decoded).toBe("World!");
    });

    test("should handle binary data", () => {
      const bytes = new Uint8Array([0, 1, 2, 255, 254, 253]);
      const dataView = new DataView(bytes.buffer);
      const base64 = dataViewToBase64(dataView);

      // Verify round-trip
      const decoded = atob(base64);
      const decodedBytes = new Uint8Array(decoded.length);
      for (let i = 0; i < decoded.length; i++) {
        decodedBytes[i] = decoded.charCodeAt(i);
      }
      expect([...decodedBytes]).toEqual([0, 1, 2, 255, 254, 253]);
    });
  });

  describe("round-trip conversions", () => {
    test("Uint8Array to base64 and back", () => {
      const original = new Uint8Array([1, 2, 3, 255, 128, 0]);
      const base64 = uint8ArrayToBase64(original);
      const result = base64ToUint8Array(base64);
      expect(result).toEqual(original);
    });

    test("DataView to base64 and back", () => {
      const buffer = new ArrayBuffer(4);
      const original = new DataView(buffer);
      original.setUint32(0, 0x12_34_56_78);
      const base64 = dataViewToBase64(original);
      const result = base64ToDataView(base64);
      expect(result.getUint32(0)).toBe(0x12_34_56_78);
    });
  });
});
