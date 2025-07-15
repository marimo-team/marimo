/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, expect, it } from "vitest";
import { groupCellsByColumn } from "../vertical-layout";

describe("groupCellsByColumn", () => {
  it("should group cells by column and maintain order", () => {
    const cells = [
      { config: { column: 0 }, id: "1" },
      { config: { column: 1 }, id: "2" },
      { config: { column: 0 }, id: "3" },
      { config: { column: 2 }, id: "4" },
      { config: { column: 1 }, id: "5" },
    ] as any[];

    const result = groupCellsByColumn(cells);

    expect(result).toEqual([
      [0, [cells[0], cells[2]]],
      [1, [cells[1], cells[4]]],
      [2, [cells[3]]],
    ]);
  });

  it("should use last seen column when column not specified", () => {
    const cells = [
      { config: { column: 0 }, id: "1" },
      { config: {}, id: "2" },
      { config: { column: 1 }, id: "3" },
      { config: {}, id: "4" },
    ] as any[];

    const result = groupCellsByColumn(cells);

    expect(result).toEqual([
      [0, [cells[0], cells[1]]],
      [1, [cells[2], cells[3]]],
    ]);
  });
});
