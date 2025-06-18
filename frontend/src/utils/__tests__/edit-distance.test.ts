/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import {
  applyOperationsWithStub,
  type EditOperation,
  editDistance,
  editDistanceGeneral,
  mergeArray,
  OperationType,
} from "../edit-distance";

describe("editDistance", () => {
  it("should return distance 0 for identical arrays", () => {
    const arr1 = ["a", "b", "c"];
    const arr2 = ["a", "b", "c"];
    const result = editDistance(arr1, arr2);

    expect(result.distance).toBe(0);
    expect(result.operations).toHaveLength(3);
    expect(
      result.operations.every((op) => op.type === OperationType.MATCH),
    ).toBe(true);
  });

  it("should handle empty arrays", () => {
    const result1 = editDistance([], []);
    expect(result1.distance).toBe(0);
    expect(result1.operations).toHaveLength(0);

    const result2 = editDistance(["a"], []);
    expect(result2.distance).toBe(1);
    expect(result2.operations).toHaveLength(1);
    expect(result2.operations[0].type).toBe(OperationType.DELETE);

    const result3 = editDistance([], ["a"]);
    expect(result3.distance).toBe(1);
    expect(result3.operations).toHaveLength(1);
    expect(result3.operations[0].type).toBe(OperationType.INSERT);
  });

  it("should handle single element differences", () => {
    const arr1 = ["a", "b", "c"];
    const arr2 = ["a", "b", "d"];
    const result = editDistance(arr1, arr2);

    expect(result.distance).toBe(1);
    expect(result.operations).toHaveLength(3);
    expect(result.operations[0].type).toBe(OperationType.MATCH);
    expect(result.operations[1].type).toBe(OperationType.MATCH);
    expect(result.operations[2].type).toBe(OperationType.SUBSTITUTE);
  });

  it("should handle insertions and deletions", () => {
    const arr1 = ["a", "b", "c"];
    const arr2 = ["a", "x", "b", "c"];
    const result = editDistance(arr1, arr2);

    expect(result.distance).toBe(1);
    expect(result.operations).toHaveLength(4);
    expect(result.operations[0].type).toBe(OperationType.MATCH);
    expect(result.operations[1].type).toBe(OperationType.INSERT);
    expect(result.operations[2].type).toBe(OperationType.MATCH);
    expect(result.operations[3].type).toBe(OperationType.MATCH);
  });

  it("should work with custom equality function", () => {
    const arr1 = [
      { id: 1, name: "a" },
      { id: 2, name: "b" },
    ];
    const arr2 = [
      { id: 1, name: "a" },
      { id: 3, name: "c" },
    ];

    const result = editDistanceGeneral(arr1, arr2, (a, b) => a.id === b.id);

    expect(result.distance).toBe(1);
    expect(result.operations).toHaveLength(2);
    expect(result.operations[0].type).toBe(OperationType.MATCH);
    expect(result.operations[1].type).toBe(OperationType.SUBSTITUTE);
  });

  // Test the specific example mentioned by the user
  it("should handle the specific example: abcde -> aczeg", () => {
    const arr1 = ["a", "b", "c", "d", "e"];
    const arr2 = ["a", "c", "z", "e", "g"];
    const result = editDistance(arr1, arr2);

    expect(result.distance).toBe(3);
    expect(result.operations).toHaveLength(6);

    // Expected operations: match, delete, match, sub, match, insert
    expect(result.operations[0].type).toBe(OperationType.MATCH); // 'a'
    expect(result.operations[1].type).toBe(OperationType.DELETE); // 'b'
    expect(result.operations[2].type).toBe(OperationType.MATCH); // 'c'
    expect(result.operations[3].type).toBe(OperationType.SUBSTITUTE); // 'd' -> 'z'
    expect(result.operations[4].type).toBe(OperationType.MATCH); // 'e'
    expect(result.operations[5].type).toBe(OperationType.INSERT); // 'g'
  });
});

describe("applyOperationsWithStub", () => {
  it("should apply match operations correctly", () => {
    const original = ["a", "b", "c"];
    const operations: Array<EditOperation> = [
      { type: OperationType.MATCH, position: 0 },
      { type: OperationType.MATCH, position: 1 },
      { type: OperationType.MATCH, position: 2 },
    ];

    const result = applyOperationsWithStub(original, operations, "stub");
    expect(result).toEqual(["a", "b", "c"]);
  });

  it("should apply delete operations correctly", () => {
    const original = ["a", "b", "c"];
    const operations: Array<EditOperation> = [
      { type: OperationType.MATCH, position: 0 },
      { type: OperationType.DELETE, position: 1 },
      { type: OperationType.MATCH, position: 2 },
    ];

    const result = applyOperationsWithStub(original, operations, "stub");
    expect(result).toEqual(["a", "c"]);
  });

  it("should apply insert operations correctly", () => {
    const original = ["a", "c"];
    const operations: Array<EditOperation> = [
      { type: OperationType.MATCH, position: 0 },
      { type: OperationType.INSERT, position: 1 },
      { type: OperationType.MATCH, position: 1 },
    ];

    const result = applyOperationsWithStub(original, operations, "stub");
    expect(result).toEqual(["a", "stub", "c"]);
  });

  it("should apply substitute operations correctly", () => {
    const original = ["a", "b", "c"];
    const operations: Array<EditOperation> = [
      { type: OperationType.MATCH, position: 0 },
      {
        type: OperationType.SUBSTITUTE,
        position: 1,
      },
      { type: OperationType.MATCH, position: 2 },
    ];

    const result = applyOperationsWithStub(original, operations, "stub");
    expect(result).toEqual(["a", "stub", "c"]);
  });

  it("should handle complex operations with position offsets", () => {
    const original = ["a", "b", "c", "d"];
    const operations: Array<EditOperation> = [
      { type: OperationType.MATCH, position: 0 },
      { type: OperationType.DELETE, position: 1 },
      { type: OperationType.INSERT, position: 1 },
      { type: OperationType.MATCH, position: 2 },
      { type: OperationType.DELETE, position: 3 },
    ];

    const result = applyOperationsWithStub(original, operations, "stub");
    expect(result).toEqual(["a", "stub", "c"]);
  });

  // Test the specific example mentioned by the user
  it("should handle the specific example: abcde -> ac_e_ (with stub)", () => {
    const original = ["a", "b", "c", "d", "e"];
    const operations: Array<EditOperation> = [
      { type: OperationType.MATCH, position: 0 },
      { type: OperationType.DELETE, position: 1 },
      { type: OperationType.MATCH, position: 2 },
      {
        type: OperationType.SUBSTITUTE,
        position: 3,
      },
      { type: OperationType.MATCH, position: 4 },
      { type: OperationType.INSERT, position: 5 },
    ];

    const result = applyOperationsWithStub(original, operations, "_");
    expect(result).toEqual(["a", "c", "_", "e", "_"]);
  });

  it("should handle multiple consecutive operations correctly", () => {
    const original = ["a", "b", "c"];
    const operations: Array<EditOperation> = [
      { type: OperationType.DELETE, position: 0 },
      { type: OperationType.INSERT, position: 0 },
      {
        type: OperationType.SUBSTITUTE,
        position: 1,
      },
      { type: OperationType.DELETE, position: 2 },
    ];

    const result = applyOperationsWithStub(original, operations, "stub");
    // After DELETE at position 0: ["b", "c"] (offset = -1)
    // After INSERT at position 0: ["stub", "b", "c"] (offset = 0)
    // After SUBSTITUTE at position 1: ["stub", "stub", "c"] (offset = 0)
    // After DELETE at position 2: ["stub", "stub"] (offset = -1)
    expect(result).toEqual(["stub", "stub"]);
  });

  it("should handle operations that affect array length", () => {
    const original = ["a", "b"];
    const operations: Array<EditOperation> = [
      { type: OperationType.INSERT, position: 0 },
      { type: OperationType.INSERT, position: 1 },
      { type: OperationType.MATCH, position: 2 },
      { type: OperationType.MATCH, position: 3 },
      { type: OperationType.INSERT, position: 4 },
    ];

    const result = applyOperationsWithStub(original, operations, "stub");
    // After INSERT at position 0: ["stub", "a", "b"] (offset = 1)
    // After INSERT at position 1: ["stub", "stub", "a", "b"] (offset = 2)
    // After MATCH at position 2: ["stub", "stub", "a", "b"] (offset = 2)
    // After MATCH at position 3: ["stub", "stub", "a", "b"] (offset = 2)
    // After INSERT at position 4: ["stub", "stub", "a", "b", "stub"] (offset = 3)
    expect(result).toEqual(["stub", "stub", "a", "b", "stub"]);
  });
});

describe("mergeArray", () => {
  it("should merge arrays with matching elements", () => {
    const arr1 = ["a", "b", "c"];
    const arr2 = ["a", "b", "c"];
    const stub = "stub";

    const result = mergeArray(arr1, arr2, (a, b) => a === b, stub);

    expect(result.merged).toEqual(["a", "b", "c"]);
    expect(result.edits.distance).toBe(0);
  });

  it("should merge arrays with different elements", () => {
    const arr1 = ["a", "b", "c"];
    const arr2 = ["a", "x", "c"];
    const stub = "stub";

    const result = mergeArray(arr1, arr2, (a, b) => a === b, stub);

    expect(result.merged).toEqual(["a", "stub", "c"]);
    expect(result.edits.distance).toBe(1);
  });

  it("should handle empty arrays", () => {
    const arr1: string[] = [];
    const arr2: string[] = [];
    const stub = "stub";

    const result = mergeArray(arr1, arr2, () => false, stub);

    expect(result.merged).toEqual([]);
    expect(result.edits.distance).toBe(0);
  });

  it("should handle one empty array", () => {
    const arr1 = ["a", "b"];
    const arr2: string[] = [];
    const stub = "stub";

    const result = mergeArray(arr1, arr2, () => false, stub);

    expect(result.merged).toEqual([]);
    expect(result.edits.distance).toBe(2);
  });

  it("should handle complex merging scenarios", () => {
    const arr1 = ["a", "b", "c"];
    const arr2 = ["a", "x", "y", "c"];
    const stub = "stub";

    const result = mergeArray(arr1, arr2, (a, b) => a === b, stub);

    expect(result.merged).toEqual(["a", "stub", "stub", "c"]);
    expect(result.edits.distance).toBe(2);
  });

  it("should handle the specific example: abcde -> aczeg", () => {
    const arr1 = ["a", "b", "c", "d", "e"];
    const arr2 = ["a", "c", "z", "e", "g"];
    const stub = "_";

    const result = mergeArray(arr1, arr2, (a, b) => a === b, stub);

    // For abcde -> aczeg:
    // a matches a -> keep a
    // b is deleted -> skip b
    // c matches c -> keep c
    // d is substituted with z -> use stub _
    // e matches e -> keep e
    // g is inserted -> use stub _
    expect(result.merged).toEqual(["a", "c", "_", "e", "_"]);
    expect(result.edits.distance).toBe(3);
  });
});
