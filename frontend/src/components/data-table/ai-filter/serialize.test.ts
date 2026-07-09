/* Copyright 2026 Marimo. All rights reserved. */

import { parseQuery } from "better-filter-bar";
import { describe, expect, it } from "vitest";
import type { FilterGroupType } from "@/plugins/impl/data-frames/schema";
import type { FieldTypesWithExternalType } from "../types";
import { fieldTypesToFilterSchema } from "./schema";
import {
  filterBarAstToMarimo,
  mergeFilterGroups,
  type SerializedFilter,
} from "./serialize";

const fieldTypes: FieldTypesWithExternalType = [
  ["status", ["string", "object"]],
  ["author", ["string", "object"]],
  ["priority", ["integer", "int64"]],
  ["price", ["number", "float64"]],
  ["year_built", ["integer", "int64"]],
  ["created", ["date", "date"]],
  ["is_active", ["boolean", "bool"]],
];

const schema = fieldTypesToFilterSchema(fieldTypes);

function serialize(query: string): SerializedFilter {
  return filterBarAstToMarimo(parseQuery(query, schema), fieldTypes);
}

// Terse builders that mirror the marimo FilterGroup shape.
function cond(
  column_id: string,
  operator: string,
  extra: Record<string, unknown> = {},
) {
  return { type: "condition", column_id, operator, negate: false, ...extra };
}
function group(operator: "and" | "or", children: unknown[]) {
  return { type: "group", operator, children, negate: false };
}

describe("filterBarAstToMarimo", () => {
  it("maps a text `:` filter to contains", () => {
    expect(serialize("status:open")).toEqual({
      filters: group("and", [cond("status", "contains", { value: "open" })]),
      query: "",
    });
  });

  it("maps numeric comparisons directly", () => {
    expect(serialize("priority>=2")).toEqual({
      filters: group("and", [cond("priority", ">=", { value: 2 })]),
      query: "",
    });
  });

  it("maps multi-value `field:(a,b)` to `in`", () => {
    expect(serialize("status:(open,closed)")).toEqual({
      filters: group("and", [
        cond("status", "in", { value: ["open", "closed"] }),
      ]),
      query: "",
    });
  });

  it("maps NOT to a negated condition", () => {
    expect(serialize("NOT status:closed")).toEqual({
      filters: group("and", [
        cond("status", "contains", { value: "closed", negate: true }),
      ]),
      query: "",
    });
  });

  it("maps AND / OR to and/or groups", () => {
    expect(serialize("status:open AND author:alice")).toEqual({
      filters: group("and", [
        cond("status", "contains", { value: "open" }),
        cond("author", "contains", { value: "alice" }),
      ]),
      query: "",
    });
    expect(serialize("status:open OR status:closed")).toEqual({
      filters: group("or", [
        cond("status", "contains", { value: "open" }),
        cond("status", "contains", { value: "closed" }),
      ]),
      query: "",
    });
  });

  it("handles the homes example (numeric comparisons under AND)", () => {
    expect(serialize("year_built:<2000 AND price:<2000000")).toEqual({
      filters: group("and", [
        cond("year_built", "<", { value: 2000 }),
        cond("price", "<", { value: 2000000 }),
      ]),
      query: "",
    });
  });

  it("preserves ISO date values for date comparisons", () => {
    expect(serialize("created:>2024-01-01")).toEqual({
      filters: group("and", [cond("created", ">", { value: "2024-01-01" })]),
      query: "",
    });
  });

  it("maps boolean truthiness to is_true / is_false", () => {
    expect(serialize("is_active:true")).toEqual({
      filters: group("and", [cond("is_active", "is_true")]),
      query: "",
    });
    expect(serialize("is_active:false")).toEqual({
      filters: group("and", [cond("is_active", "is_false")]),
      query: "",
    });
  });

  it("routes free text into the query while keeping structured filters", () => {
    const result = serialize('label:"needs review" homes');
    expect(result.query).toBe("homes");
    // `label` is unknown to the schema, so it defaults to a text contains match.
    expect(result.filters).toEqual(
      group("and", [cond("label", "contains", { value: "needs review" })]),
    );
  });

  it("nests a grouped OR inside an AND", () => {
    expect(serialize("(status:open OR status:draft) AND priority>=3")).toEqual({
      filters: group("and", [
        group("or", [
          cond("status", "contains", { value: "open" }),
          cond("status", "contains", { value: "draft" }),
        ]),
        cond("priority", ">=", { value: 3 }),
      ]),
      query: "",
    });
  });

  it("returns null filters for empty and free-text-only queries", () => {
    expect(serialize("")).toEqual({ filters: null, query: "" });
    const freeOnly = serialize("just some text");
    expect(freeOnly.filters).toBeNull();
    expect(freeOnly.query).toContain("just");
  });
});

describe("mergeFilterGroups", () => {
  // Real, properly-typed FilterGroupType values.
  const a = serialize("priority>=2").filters as FilterGroupType;
  const b = serialize("status:open OR status:closed")
    .filters as FilterGroupType;
  const empty: FilterGroupType = {
    type: "group",
    operator: "and",
    children: [],
    negate: false,
  };

  it("returns base when extra is null or empty", () => {
    expect(mergeFilterGroups(a, null)).toEqual(a);
    expect(mergeFilterGroups(a, empty)).toEqual(a);
  });

  it("returns extra when base is empty", () => {
    expect(mergeFilterGroups(empty, b)).toEqual(b);
  });

  it("ANDs two non-empty groups together", () => {
    expect(mergeFilterGroups(a, b)).toEqual(group("and", [a, b]));
  });
});
