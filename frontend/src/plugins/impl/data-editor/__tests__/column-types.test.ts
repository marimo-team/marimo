/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, describe, expect, it, vi } from "vitest";
import { vegaLoadData, vegaLoader } from "../../vega/loader";
import { normalizeConfiguredColumns } from "../column-types";
import type { EditorRow } from "../types";

describe("normalizeConfiguredColumns", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("preserves the data reference when no columns are configured", () => {
    const data = [{ label: "01", done: "yes" }];
    expect(normalizeConfiguredColumns(data, new Map())).toBe(data);
  });

  it("normalizes large integer boolean values from the CSV loader", async () => {
    vi.spyOn(vegaLoader, "load").mockResolvedValueOnce(
      "done,label\n9007199254740992,01\n-9007199254740992,02\n0,03\n",
    );

    const data = await vegaLoadData<EditorRow>(
      "data.csv",
      { type: "csv", parse: { done: "integer", label: "string" } },
      { handleBigIntAndNumberLike: true },
    );

    expect(data).toEqual([
      { done: BigInt("9007199254740992"), label: "01" },
      { done: BigInt("-9007199254740992"), label: "02" },
      { done: 0, label: "03" },
    ]);
    expect(
      normalizeConfiguredColumns(data, new Map([["done", "boolean"]])),
    ).toEqual([
      { done: true, label: "01" },
      { done: true, label: "02" },
      { done: false, label: "03" },
    ]);
  });
});
