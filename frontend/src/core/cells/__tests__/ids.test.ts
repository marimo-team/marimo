/* Copyright 2024 Marimo. All rights reserved. */
import { expect, describe, test } from "vitest";
import { CellId, CellOutputId, HTMLCellId, findCellId } from "../ids";
import { renderHook } from "@testing-library/react";

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

describe("CellOutputId", () => {
  test("create", () => {
    const cellId = CellId.create();
    const cellOutputId = CellOutputId.create(cellId);
    expect(cellOutputId).toBe(`output-${cellId}`);
  });
});

describe("useFindCellId", () => {
  test("finds cell ID in normal DOM", () => {
    const cellId = CellId.create();
    const htmlCellId = HTMLCellId.create(cellId);

    // Create a div with the cell ID
    const div = document.createElement("div");
    div.id = htmlCellId;
    document.body.append(div);

    // Create a ref to a child element
    const childDiv = document.createElement("div");
    div.append(childDiv);
    const ref = { current: childDiv };

    const { result } = renderHook(() => findCellId(ref));

    // Hook should find the cell ID
    expect(result.current).toBe(cellId);

    // Cleanup
    div.remove();
  });

  test("finds cell ID through shadow DOM", () => {
    const cellId = CellId.create();
    const htmlCellId = HTMLCellId.create(cellId);

    // Create a div with the cell ID
    const div = document.createElement("div");
    div.id = htmlCellId;
    document.body.append(div);

    // Create a shadow DOM with a child element
    const shadow = div.attachShadow({ mode: "open" });
    const shadowChild = document.createElement("div");
    shadow.append(shadowChild);

    // Create a ref to a deeply nested element
    const nestedDiv = document.createElement("div");
    shadowChild.append(nestedDiv);
    const ref = { current: nestedDiv };

    const { result } = renderHook(() => findCellId(ref));

    // Hook should find the cell ID through shadow DOM
    expect(result.current).toBe(cellId);

    // Cleanup
    div.remove();
  });

  test("returns null when no cell ID is found", () => {
    // Create a div without a cell ID
    const div = document.createElement("div");
    document.body.append(div);
    const ref = { current: div };

    const { result } = renderHook(() => findCellId(ref));

    // Hook should return null when no cell ID is found
    expect(result.current).toBeNull();

    // Cleanup
    div.remove();
  });
});
