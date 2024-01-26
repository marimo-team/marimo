/* Copyright 2024 Marimo. All rights reserved. */

import {
  normalizeName,
  DEFAULT_CELL_NAME,
  getValidName,
  displayCellName,
} from "../names";
import { expect, describe, it } from "vitest";

describe("normalizeName", () => {
  it("should return the default cell name for empty input", () => {
    expect(normalizeName("")).toBe(DEFAULT_CELL_NAME);
    expect(normalizeName(" ")).toBe(DEFAULT_CELL_NAME);
    expect(normalizeName("  ")).toBe(DEFAULT_CELL_NAME);
    expect(normalizeName("   ")).toBe(DEFAULT_CELL_NAME);
  });

  it("should remove special characters and make lowercase", () => {
    expect(normalizeName("Test Name!")).toBe("test_name_");
    expect(normalizeName("Another Name")).toBe("another_name");
    expect(normalizeName("Some name 10")).toBe("some_name_10");
    expect(normalizeName("10 names")).toBe("_10_names");
  });
});

describe("getValidName", () => {
  it("should return the same name if it is not in the set", () => {
    expect(getValidName("new_name", ["other"])).toBe("new_name");
  });

  it("should return a non-conflicting name", () => {
    expect(getValidName("name", ["name"])).toBe("name_1");
    expect(getValidName("name", ["name_1", "name"])).toBe("name_2");
  });

  it("should avoid names that are in the disallowed set", () => {
    expect(getValidName("None", [])).toBe("None_1");
    expect(getValidName("None", ["None_1"])).toBe("None_2");

    expect(getValidName("marimo", [])).toBe("marimo_1");
    expect(getValidName("app", [])).toBe("app_1");
    expect(getValidName("continue", [])).toBe("continue_1");
  });
});

describe("displayCellName", () => {
  it("should return the name if it is not the default cell name", () => {
    expect(displayCellName("custom_name", 1)).toBe("custom_name");
  });

  it("should return the HTML cell ID if the name is the default cell name", () => {
    expect(displayCellName(DEFAULT_CELL_NAME, 0)).toBe("cell-0");
    expect(displayCellName(DEFAULT_CELL_NAME, 1)).toBe("cell-1");
  });
});
