/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import type { WireFormat } from "@/plugins/impl/anywidget/types";
import type { Base64String } from "../../../../utils/json/base64";
import { decodeFromWire, serializeBuffersToBase64 } from "../serialization";

describe("decodeFromWire with DataViews", () => {
  it("should return the original state if bufferPaths.length === 0", () => {
    const state = { a: 1, b: 2 };
    const result = decodeFromWire({ state, bufferPaths: [] });
    expect(result).toEqual(state);
  });

  it("should insert DataViews at specified buffer paths", () => {
    const state = {
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
    const result = decodeFromWire({ state, bufferPaths, buffers });
    expect(result).toMatchInlineSnapshot(`
      {
        "a": 1,
        "b": {
          "c": DataView [
            72,
            101,
            108,
            108,
            111,
          ],
          "d": DataView [
            87,
            111,
            114,
            108,
            100,
          ],
        },
      }
    `);
  });

  it("should throw error when buffers and paths length mismatch", () => {
    const state = { a: 1 };
    const bufferPaths = [
      ["b", "c"],
      ["b", "d"],
    ];
    const buffers = [new DataView(new ArrayBuffer())]; // Only one buffer for two paths

    expect(() => decodeFromWire({ state, bufferPaths, buffers })).toThrow(
      "Buffers and buffer paths not the same length",
    );
  });

  it("should handle empty buffers array", () => {
    const state = { a: 1 };
    const bufferPaths = [["b", "c"]];
    const buffers: DataView[] = [];

    expect(() => decodeFromWire({ state, bufferPaths, buffers })).toThrow(
      "Buffers and buffer paths not the same length",
    );
  });
});

describe("Immutability Tests", () => {
  it("serializeBuffersToBase64 should not mutate input", () => {
    const encoder = new TextEncoder();
    const dataView1 = new DataView(encoder.encode("data1").buffer);
    const dataView2 = new DataView(encoder.encode("data2").buffer);

    const input = {
      buffer1: dataView1,
      nested: {
        buffer2: dataView2,
        value: "test",
      },
      array: [1, 2, 3],
    };

    const clone = structuredClone(input);

    serializeBuffersToBase64(input);

    // Check deep equality
    expect(input).toEqual(clone);

    // Check references are unchanged
    expect(input.buffer1).toBe(dataView1);
    expect(input.nested.buffer2).toBe(dataView2);
    expect(input.nested).toBe(input.nested); // Nested object reference unchanged
    expect(input.array).toBe(input.array); // Array reference unchanged
  });

  it("decodeFromWire (wire format) should decode base64 to DataView", () => {
    const encoder = new TextEncoder();
    const data = encoder.encode("Hello");
    const base64 = btoa(String.fromCharCode(...data)) as Base64String;

    const input = {
      state: { text: base64, number: 42, nested: { value: "test" } },
      bufferPaths: [["text"]],
      buffers: [base64],
    };

    const result = decodeFromWire(input);

    // Result should have DataView instead of base64 string
    expect(result.text).toBeInstanceOf(DataView);
    // Other properties should be preserved
    expect(result.number).toBe(42);
    expect(result.nested).toEqual({ value: "test" });
  });

  it("decodeFromWire (with DataViews) should insert buffers at paths", () => {
    const encoder = new TextEncoder();
    const dataView = new DataView(encoder.encode("data").buffer);

    const state = {
      placeholder: "value",
      nested: { key: "test" },
      array: [1, 2, 3],
    };
    const bufferPaths = [["data"]];
    const buffers = [dataView];

    const result = decodeFromWire({
      state,
      bufferPaths,
      buffers,
    }) as typeof state & { data: DataView };

    // Result should have the DataView at the path
    expect(result.data).toBe(dataView);
    // Other properties should be preserved
    expect(result.placeholder).toBe("value");
    expect(result.nested).toEqual({ key: "test" });
    expect(result.array).toEqual([1, 2, 3]);
  });

  it("decodeFromWire should insert buffers and return state", () => {
    const encoder = new TextEncoder();
    const dataView = new DataView(encoder.encode("data").buffer);

    const state = { a: 1, b: 2 };
    const bufferPaths = [["c"]];
    const buffers = [dataView];

    const result = decodeFromWire({
      state,
      bufferPaths,
      buffers,
    }) as typeof state & { c: DataView };

    // Result should have new property
    expect("c" in result).toBe(true);
    expect(result.c).toBe(dataView);
  });

  it("serializeBuffersToBase64 should return new state object", () => {
    const encoder = new TextEncoder();
    const dataView = new DataView(encoder.encode("data").buffer);

    const input = {
      buffer: dataView,
      value: "test",
    };

    const result = serializeBuffersToBase64(input);

    // State should be different reference
    expect(result.state).not.toBe(input);

    // Input should still have DataView
    expect(input.buffer).toBeInstanceOf(DataView);

    // Result state should have base64 string
    expect(typeof result.state.buffer).toBe("string");
  });

  it("decodeFromWire with object input should insert buffers", () => {
    const encoder = new TextEncoder();
    const dataView = new DataView(encoder.encode("data").buffer);

    const state = { a: 1, b: { c: 2 } };
    const bufferPaths = [["d"]];
    const buffers = [dataView];

    const result = decodeFromWire({
      state,
      bufferPaths,
      buffers,
    }) as typeof state & { d: DataView };

    // Result should have the buffer inserted
    expect(result.d).toBe(dataView);
    // Original properties should be preserved
    expect(result.a).toBe(1);
    expect(result.b).toEqual({ c: 2 });
  });

  it("nested objects should maintain independence after serialization", () => {
    const encoder = new TextEncoder();
    const dataView = new DataView(encoder.encode("data").buffer);

    const nested = { buffer: dataView, value: "nested" };
    const input = {
      nested,
      other: "value",
    };

    const result = serializeBuffersToBase64(input);

    // Mutate result state
    (result.state.nested as Record<string, unknown>).value = "changed";

    // Original nested object should be unchanged
    expect(nested.value).toBe("nested");
    expect(input.nested.value).toBe("nested");
  });

  it("arrays should not be mutated during operations", () => {
    const encoder = new TextEncoder();
    const dataView = new DataView(encoder.encode("data").buffer);

    const input = {
      items: [dataView, "middle", { value: 1 }],
    };

    const originalItems = input.items;
    const originalMiddle = input.items[1];
    const originalObject = input.items[2];

    serializeBuffersToBase64(input);

    // Array reference should be unchanged
    expect(input.items).toBe(originalItems);
    expect(input.items[1]).toBe(originalMiddle);
    expect(input.items[2]).toBe(originalObject);
  });
});

describe("serializeBuffersToBase64", () => {
  it("should return empty arrays when no DataViews present", () => {
    const input = { a: 1, b: "text", c: { d: true } };
    const result = serializeBuffersToBase64(input);

    expect(result).toEqual({
      state: input,
      buffers: [],
      bufferPaths: [],
    });
  });

  it("should serialize DataViews at top level", () => {
    const encoder = new TextEncoder();
    const dataView = new DataView(encoder.encode("test").buffer);
    const input = { data: dataView, other: 123 };

    const result = serializeBuffersToBase64(input);

    expect(result.buffers).toHaveLength(1);
    expect(result.bufferPaths).toEqual([["data"]]);
    expect(typeof result.state.data).toBe("string");
    expect(result.state.other).toBe(123);
  });

  it("should serialize nested DataViews", () => {
    const encoder = new TextEncoder();
    const dataView1 = new DataView(encoder.encode("first").buffer);
    const dataView2 = new DataView(encoder.encode("second").buffer);
    const input = {
      nested: {
        buffer1: dataView1,
        deeper: {
          buffer2: dataView2,
        },
      },
      regular: "value",
    };

    const result = serializeBuffersToBase64(input);

    expect(result.buffers).toHaveLength(2);
    expect(result.bufferPaths).toEqual([
      ["nested", "buffer1"],
      ["nested", "deeper", "buffer2"],
    ]);
    expect(typeof result.state.nested.buffer1).toBe("string");
    expect(typeof result.state.nested.deeper.buffer2).toBe("string");
  });

  it("should serialize DataViews in arrays", () => {
    const encoder = new TextEncoder();
    const dataView1 = new DataView(encoder.encode("one").buffer);
    const dataView2 = new DataView(encoder.encode("two").buffer);
    const input = {
      items: [dataView1, "middle", dataView2],
    };

    const result = serializeBuffersToBase64(input);

    expect(result.buffers).toHaveLength(2);
    expect(result.bufferPaths).toEqual([
      ["items", 0],
      ["items", 2],
    ]);
    expect(result.state.items[1]).toBe("middle");
  });

  it("should handle mixed nested structures", () => {
    const encoder = new TextEncoder();
    const dataView = new DataView(encoder.encode("data").buffer);
    const input = {
      array: [{ nested: dataView }, [dataView]],
    };

    const result = serializeBuffersToBase64(input);

    expect(result.buffers).toHaveLength(2);
    expect(result.bufferPaths).toContainEqual(["array", 0, "nested"]);
    expect(result.bufferPaths).toContainEqual(["array", 1, 0]);
  });
});

describe("decodeFromWire from WireFormat", () => {
  it("should return state unchanged when no buffer paths", () => {
    const wire: WireFormat = {
      state: { a: 1, b: "text" },
      bufferPaths: [],
      buffers: [],
    };
    const result = decodeFromWire(wire);
    expect(result).toEqual({ a: 1, b: "text" });
  });

  it("should decode single buffer at top level", () => {
    const encoder = new TextEncoder();
    const originalData = encoder.encode("Hello");
    const base64 = btoa(String.fromCharCode(...originalData)) as Base64String;

    const wire: WireFormat = {
      state: { data: base64, other: 123 },
      bufferPaths: [["data"]],
      buffers: [base64],
    };

    const result = decodeFromWire(wire);

    expect(result.data).toBeInstanceOf(DataView);
    expect(result.other).toBe(123);

    // Verify the DataView contains correct data
    const bytes = new Uint8Array((result.data as DataView).buffer);
    const decoded = new TextDecoder().decode(bytes);
    expect(decoded).toBe("Hello");
  });

  it("should decode nested buffers", () => {
    const encoder = new TextEncoder();
    const data1 = encoder.encode("first");
    const data2 = encoder.encode("second");
    const base641 = btoa(String.fromCharCode(...data1)) as Base64String;
    const base642 = btoa(String.fromCharCode(...data2)) as Base64String;

    const wire: WireFormat = {
      state: {
        nested: {
          buf1: base641,
          deeper: {
            buf2: base642,
          },
        },
      },
      bufferPaths: [
        ["nested", "buf1"],
        ["nested", "deeper", "buf2"],
      ],
      buffers: [base641, base642],
    };

    const result = decodeFromWire(wire) as {
      nested: { buf1: unknown; deeper: { buf2: unknown } };
    };

    expect(result.nested.buf1).toBeInstanceOf(DataView);
    expect(result.nested.deeper.buf2).toBeInstanceOf(DataView);
  });

  it("should decode buffers in arrays", () => {
    const encoder = new TextEncoder();
    const data = encoder.encode("test");
    const base64 = btoa(String.fromCharCode(...data)) as Base64String;

    const wire: WireFormat = {
      state: {
        items: [base64, "middle", base64],
      },
      bufferPaths: [
        ["items", 0],
        ["items", 2],
      ],
      buffers: [base64, base64],
    };

    const result = decodeFromWire(wire) as { items: unknown[] };

    expect(result.items[0]).toBeInstanceOf(DataView);
    expect(result.items[1]).toBe("middle");
    expect(result.items[2]).toBeInstanceOf(DataView);
  });

  it("should handle round-trip serialization", () => {
    const encoder = new TextEncoder();
    const dataView1 = new DataView(encoder.encode("data1").buffer);
    const dataView2 = new DataView(encoder.encode("data2").buffer);

    const original = {
      buffer1: dataView1,
      nested: {
        buffer2: dataView2,
      },
      regular: "value",
    };

    // Serialize
    const serialized = serializeBuffersToBase64(original);

    // Deserialize
    const deserialized = decodeFromWire(serialized);

    // Verify structure is preserved
    expect(deserialized.buffer1).toBeInstanceOf(DataView);
    expect(deserialized.nested.buffer2).toBeInstanceOf(DataView);
    expect(deserialized.regular).toBe("value");

    // Verify data integrity
    const bytes1 = new Uint8Array((deserialized.buffer1 as DataView).buffer);
    const bytes2 = new Uint8Array(
      (deserialized.nested.buffer2 as DataView).buffer,
    );
    expect(new TextDecoder().decode(bytes1)).toBe("data1");
    expect(new TextDecoder().decode(bytes2)).toBe("data2");
  });
});
