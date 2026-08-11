/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type { DataType } from "@/core/kernel/messages";
import { DATA_TYPE_ICON, resolveDataType } from "../icons";

describe("resolveDataType", () => {
  it("passes through every mapped data type", () => {
    for (const dataType of Object.keys(DATA_TYPE_ICON)) {
      expect(resolveDataType(dataType as DataType)).toBe(dataType);
    }
  });

  it("resolves unmapped data types to unknown", () => {
    expect(resolveDataType("geometry" as DataType)).toBe("unknown");
  });

  it("resolves data types shadowing Object.prototype keys to unknown", () => {
    expect(resolveDataType("toString" as DataType)).toBe("unknown");
  });
});
