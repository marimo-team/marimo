/* Copyright 2023 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-non-null-assertion */
import { expect, describe, test } from "vitest";
import { CellId, HTMLCellId } from "../ids";

describe("CellId", () => {
  test("create", () => {
    const cellId = CellId.create();
    expect(typeof cellId).toBe("string");
    expect(cellId.length).toBeGreaterThan(0);
  });
});

describe("HTMLCellId", () => {
  test("create", () => {
    const cellId = CellId.create();
    const htmlCellId = HTMLCellId.create(cellId);
    expect(htmlCellId).toBe(`cell-${cellId}`);
  });

  test("parse", () => {
    const cellId = CellId.create();
    const htmlCellId = HTMLCellId.create(cellId);
    const parsedCellId = HTMLCellId.parse(htmlCellId);
    expect(parsedCellId).toBe(cellId);
  });

  test("findElement", () => {
    document.body.innerHTML = `
      <div id="not-a-cell"></div>
      <div id="cell-${CellId.create()}">
        <div id="inner-div"></div>
      </div>
    `;
    const innerDiv = document.querySelector("#inner-div");
    expect(innerDiv).toBeDefined();
    const cell = HTMLCellId.findElement(innerDiv!);
    expect(cell).toBeDefined();
    expect(cell!.id.startsWith("cell-")).toBe(true);
  });
});
