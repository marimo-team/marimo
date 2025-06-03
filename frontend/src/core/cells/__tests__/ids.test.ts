/* Copyright 2024 Marimo. All rights reserved. */
import { expect, describe, it } from "vitest";
import { CellId, CellOutputId, HTMLCellId, findCellId } from "../ids";

describe("CellId", () => {
  it("create", () => {
    const cellId = CellId.create();
    expect(typeof cellId).toBe("string");
    expect(cellId.length).toBeGreaterThan(0);
  });
});

describe("HTMLCellId", () => {
  it("create", () => {
    const cellId = CellId.create();
    const htmlCellId = HTMLCellId.create(cellId);
    expect(htmlCellId).toBe(`cell-${cellId}`);
  });

  it("parse", () => {
    const cellId = CellId.create();
    const htmlCellId = HTMLCellId.create(cellId);
    const parsedCellId = HTMLCellId.parse(htmlCellId);
    expect(parsedCellId).toBe(cellId);
  });

  it("findElement", () => {
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

  it("create 1000 ids", () => {
    const ids: CellId[] = [];
    for (let i = 0; i < 1000; i++) {
      const id = CellId.create();
      ids.push(id);
    }
    expect(ids.length).toBe(1000);
    expect(new Set(ids).size).toBe(1000);
  });
});

describe("CellOutputId", () => {
  it("create", () => {
    const cellId = CellId.create();
    const cellOutputId = CellOutputId.create(cellId);
    expect(cellOutputId).toBe(`output-${cellId}`);
  });
});

describe("findCellId", () => {
  it("should find cell ID when element is inside a cell container", () => {
    // Create a cell container with a known ID
    const cellId = CellId.create();
    const container = document.createElement("div");
    container.id = HTMLCellId.create(cellId);

    // Create a child element inside the container
    const child = document.createElement("div");
    container.append(child);

    // Test finding the cell ID from the child element
    expect(findCellId(child)).toBe(cellId);
  });

  it("should find cell ID when element is the cell container itself", () => {
    // Create a cell container with a known ID
    const cellId = CellId.create();
    const container = document.createElement("div");
    container.id = HTMLCellId.create(cellId);

    // Test finding the cell ID from the container itself
    expect(findCellId(container)).toBe(cellId);
  });

  it("should return null when element is not inside a cell container", () => {
    // Create an element that's not inside any cell container
    const element = document.createElement("div");
    expect(findCellId(element)).toBeNull();
  });
});
