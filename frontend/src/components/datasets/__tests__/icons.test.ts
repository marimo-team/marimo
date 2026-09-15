/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type { DataType } from "@/core/kernel/messages";
import { DATA_TYPE_ICON, getDataTypeColor, resolveDataType } from "../icons";

describe("resolveDataType", () => {
  it("passes through every mapped data type", () => {
    for (const dataType of Object.keys(DATA_TYPE_ICON)) {
      expect(resolveDataType(dataType as DataType)).toBe(dataType);
    }
  });

  it("resolves unmapped data types to unknown", () => {
    expect(resolveDataType("bogus_type" as DataType)).toBe("unknown");
  });

  it("resolves geometry with its icon and color", () => {
    expect(resolveDataType("geometry")).toBe("geometry");
    expect(DATA_TYPE_ICON.geometry).toBeDefined();
    expect(getDataTypeColor("geometry")).toBe(
      "bg-(--cyan-4) dark:bg-(--cyan-5)",
    );
  });

  it("resolves data types shadowing Object.prototype keys to unknown", () => {
    expect(resolveDataType("toString" as DataType)).toBe("unknown");
  });
});
