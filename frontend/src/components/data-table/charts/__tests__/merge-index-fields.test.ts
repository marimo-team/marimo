/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type { FieldTypesWithExternalType } from "@/components/data-table/types";
import { mergeIndexFields } from "../charts";

describe("mergeIndexFields", () => {
  it("appends row-header (index) fields to field types", () => {
    const fieldTypes: FieldTypesWithExternalType = [["v", ["number", "int64"]]];
    const rowHeaders: FieldTypesWithExternalType = [
      ["k", ["string", "object"]],
    ];
    expect(mergeIndexFields(fieldTypes, rowHeaders)).toEqual([
      ["v", ["number", "int64"]],
      ["k", ["string", "object"]],
    ]);
  });

  it("de-dupes when an index name matches a column name", () => {
    const fieldTypes: FieldTypesWithExternalType = [["k", ["number", "int64"]]];
    const rowHeaders: FieldTypesWithExternalType = [
      ["k", ["string", "object"]],
    ];
    expect(mergeIndexFields(fieldTypes, rowHeaders)).toEqual([
      ["k", ["number", "int64"]],
    ]);
  });

  it("returns field types unchanged when there are no row headers", () => {
    const fieldTypes: FieldTypesWithExternalType = [["v", ["number", "int64"]]];
    expect(mergeIndexFields(fieldTypes, [])).toEqual(fieldTypes);
  });
});
