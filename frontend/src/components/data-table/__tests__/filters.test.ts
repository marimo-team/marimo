/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import {
  filterToFilterCondition,
  filtersToFilterGroup,
  Filter,
} from "../filters";
import {
  FilterConditionSchema,
  FilterGroupSchema,
} from "@/plugins/impl/data-frames/schema";

describe("filterToFilterCondition", () => {
  it("returns empty array for undefined filter", () => {
    expect(filterToFilterCondition("col", undefined)).toEqual([]);
  });

  it("handles is_null filter", () => {
    const result = filterToFilterCondition(
      "col",
      Filter.number({ operator: "is_null" }),
    );
    expect(result).toEqual([
      {
        column_id: "col",
        operator: "is_null",
        value: undefined,
        type: "condition",
        negate: false,
      },
    ]);
  });

  it("handles is_not_null filter", () => {
    const result = filterToFilterCondition(
      "col",
      Filter.number({ operator: "is_not_null" }),
    );
    expect(result).toEqual([
      {
        column_id: "col",
        operator: "is_not_null",
        value: undefined,
        type: "condition",
        negate: false,
      },
    ]);
  });

  it("handles number filter with min only", () => {
    const result = filterToFilterCondition("age", Filter.number({ min: 18 }));
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({
      column_id: "age",
      operator: ">=",
      value: 18,
      type: "condition",
      negate: false,
    });
  });

  it("handles number filter with max only", () => {
    const result = filterToFilterCondition("age", Filter.number({ max: 65 }));
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({
      column_id: "age",
      operator: "<=",
      value: 65,
      type: "condition",
      negate: false,
    });
  });

  it("handles number filter with min and max", () => {
    const result = filterToFilterCondition(
      "age",
      Filter.number({ min: 18, max: 65 }),
    );
    expect(result).toHaveLength(2);
    expect(result[0]).toMatchObject({ operator: ">=", value: 18 });
    expect(result[1]).toMatchObject({ operator: "<=", value: 65 });
  });

  it("handles text filter", () => {
    const result = filterToFilterCondition(
      "name",
      Filter.text({ text: "foo", operator: "contains" }),
    );
    expect(result).toEqual([
      {
        column_id: "name",
        operator: "contains",
        value: "foo",
        type: "condition",
        negate: false,
      },
    ]);
  });

  it("handles boolean true filter", () => {
    const result = filterToFilterCondition(
      "active",
      Filter.boolean({ value: true }),
    );
    expect(result).toEqual([
      {
        column_id: "active",
        operator: "is_true",
        value: undefined,
        type: "condition",
        negate: false,
      },
    ]);
  });

  it("handles boolean false filter", () => {
    const result = filterToFilterCondition(
      "active",
      Filter.boolean({ value: false }),
    );
    expect(result).toEqual([
      {
        column_id: "active",
        operator: "is_false",
        value: undefined,
        type: "condition",
        negate: false,
      },
    ]);
  });

  it("handles select in filter", () => {
    const result = filterToFilterCondition(
      "status",
      Filter.select({ options: ["a", "b"], operator: "in" }),
    );
    expect(result).toEqual([
      {
        column_id: "status",
        operator: "in",
        value: ["a", "b"],
        type: "condition",
        negate: false,
      },
    ]);
  });

  it("handles date filter with min and max", () => {
    const min = new Date("2024-01-01");
    const max = new Date("2024-12-31");
    const result = filterToFilterCondition(
      "created",
      Filter.date({ min, max }),
    );
    expect(result).toHaveLength(2);
    expect(result[0]).toMatchObject({
      operator: ">=",
      value: min.toISOString(),
    });
    expect(result[1]).toMatchObject({
      operator: "<=",
      value: max.toISOString(),
    });
  });

  it("every condition has type and negate fields", () => {
    const result = filterToFilterCondition(
      "col",
      Filter.number({ min: 1, max: 10 }),
    );
    for (const condition of result) {
      expect(condition).toHaveProperty("type", "condition");
      expect(condition).toHaveProperty("negate", false);
    }
  });
});

describe("filtersToFilterGroup", () => {
  it("returns empty AND group for no filters", () => {
    const result = filtersToFilterGroup([]);
    expect(result).toEqual({
      type: "group",
      operator: "and",
      children: [],
      negate: false,
    });
  });

  it("wraps single filter in AND group", () => {
    const result = filtersToFilterGroup([
      { id: "age", value: Filter.number({ min: 18 }) },
    ]);
    expect(result.type).toBe("group");
    expect(result.operator).toBe("and");
    expect(result.negate).toBe(false);
    expect(result.children).toHaveLength(1);
  });

  it("wraps multiple filters in AND group", () => {
    const result = filtersToFilterGroup([
      { id: "age", value: Filter.number({ min: 18 }) },
      { id: "name", value: Filter.text({ text: "foo", operator: "contains" }) },
    ]);
    expect(result.children).toHaveLength(2);
    expect(result.operator).toBe("and");
  });

  it("flattens multi-condition filters", () => {
    const result = filtersToFilterGroup([
      { id: "age", value: Filter.number({ min: 18, max: 65 }) },
    ]);
    // min + max = 2 conditions
    expect(result.children).toHaveLength(2);
  });
});

describe("schema validation", () => {
  it("FilterConditionSchema accepts valid condition", () => {
    const result = FilterConditionSchema.safeParse({
      column_id: "age",
      operator: ">=",
      value: 18,
    });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.type).toBe("condition");
      expect(result.data.negate).toBe(false);
    }
  });

  it("FilterConditionSchema defaults type and negate", () => {
    const result = FilterConditionSchema.safeParse({
      column_id: "age",
      operator: "==",
      value: 5,
    });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.type).toBe("condition");
      expect(result.data.negate).toBe(false);
    }
  });

  it("FilterConditionSchema accepts negate=true", () => {
    const result = FilterConditionSchema.safeParse({
      column_id: "age",
      operator: "==",
      value: 5,
      negate: true,
    });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.negate).toBe(true);
    }
  });

  it("FilterGroupSchema accepts valid group", () => {
    const result = FilterGroupSchema.safeParse({
      type: "group",
      operator: "and",
      children: [{ column_id: "age", operator: ">=", value: 18 }],
    });
    expect(result.success).toBe(true);
  });

  it("FilterGroupSchema accepts nested groups", () => {
    const result = FilterGroupSchema.safeParse({
      type: "group",
      operator: "or",
      children: [
        {
          type: "group",
          operator: "and",
          children: [
            { column_id: "a", operator: "==", value: 1 },
            { column_id: "b", operator: ">", value: 2 },
          ],
        },
        { column_id: "c", operator: "==", value: 3 },
      ],
    });
    expect(result.success).toBe(true);
  });

  it("FilterGroupSchema rejects invalid operator", () => {
    const result = FilterGroupSchema.safeParse({
      type: "group",
      operator: "xor",
      children: [],
    });
    expect(result.success).toBe(false);
  });

  it("FilterGroupSchema defaults fields", () => {
    const result = FilterGroupSchema.safeParse({});
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.type).toBe("group");
      expect(result.data.operator).toBe("and");
      expect(result.data.children).toEqual([]);
      expect(result.data.negate).toBe(false);
    }
  });
});
