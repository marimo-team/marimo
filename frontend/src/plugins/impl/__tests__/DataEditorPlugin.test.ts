/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { DataEditorPlugin } from "../DataEditorPlugin";

describe("DataEditorPlugin", () => {
  it("normalizes an unrecognized field type", () => {
    const result = DataEditorPlugin.validator.parse({
      initialValue: { edits: [] },
      label: null,
      data: [],
      fieldTypes: [["geom", ["bogus_type", "geometry"]]],
      editableColumns: "all",
    });

    expect(result.fieldTypes).toEqual([["geom", ["unknown", "geometry"]]]);
  });

  it("keeps the geometry field type", () => {
    const result = DataEditorPlugin.validator.parse({
      initialValue: { edits: [] },
      label: null,
      data: [],
      fieldTypes: [["geom", ["geometry", "geometry"]]],
      editableColumns: "all",
    });

    expect(result.fieldTypes).toEqual([["geom", ["geometry", "geometry"]]]);
  });
});
