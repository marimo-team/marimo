// Test to verify BigInt conversion in loadTableData
import { describe, expect, it } from "vitest";
import { loadTableData } from "../utils";

describe("loadTableData with BigInt conversion", () => {
  it("should convert large integer strings to BigInt", async () => {
    // JSON data similar to what the backend would send
    const jsonData = `[
      {
        "regular": 42,
        "big_list": ["599087340098420735", "599087342245904383"],
        "direct_neighbors": ["999742000000000000", "888888888888888888"]
      },
      {
        "regular": 43,
        "big_list": ["123456789012345678", "987654321098765432"]
      }
    ]`;

    const result = await loadTableData(jsonData);

    // Check that large integers are converted to BigInt
    expect(typeof result[0].big_list[0]).toBe("bigint");
    expect(result[0].big_list[0]).toBe(BigInt("599087340098420735"));

    expect(typeof result[0].direct_neighbors[0]).toBe("bigint");
    expect(result[0].direct_neighbors[0]).toBe(BigInt("999742000000000000"));

    // Check that regular integers remain as numbers
    expect(typeof result[0].regular).toBe("number");
    expect(result[0].regular).toBe(42);
  });

  it("should not convert small integer strings", async () => {
    const jsonData = `[
      {
        "small_int_string": "42",
        "large_int_string": "599087340098420735",
        "text": "hello world"
      }
    ]`;

    const result = await loadTableData(jsonData);

    // Small integer strings should remain as strings
    expect(typeof result[0].small_int_string).toBe("string");
    expect(result[0].small_int_string).toBe("42");

    // Large integer strings should become BigInt
    expect(typeof result[0].large_int_string).toBe("bigint");
    expect(result[0].large_int_string).toBe(BigInt("599087340098420735"));

    // Text should remain as string
    expect(typeof result[0].text).toBe("string");
    expect(result[0].text).toBe("hello world");
  });

  it("should handle array data without conversion", async () => {
    // When data is already an array, it should pass through without BigInt conversion
    const arrayData = [
      {
        regular: 42,
        big_string: "599087340098420735", // This will remain a string since no JSON parsing
      },
    ];

    const result = await loadTableData(arrayData);

    // Should remain as string since no JSON parsing occurred
    expect(typeof result[0].big_string).toBe("string");
    expect(result[0].big_string).toBe("599087340098420735");
  });
});