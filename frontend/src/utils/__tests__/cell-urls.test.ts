/* Copyright 2024 Marimo. All rights reserved. */
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { EDGE_CASE_CELL_NAMES } from "../../__tests__/mocks";
import {
  canLinkToCell,
  createCellLink,
  extractCellNameFromHash,
} from "../cell-urls";

describe("cell-urls utilities", () => {
  const originalLocation = window.location;

  beforeEach(() => {
    // Mock window.location for testing
    Object.defineProperty(window, "location", {
      value: {
        href: "https://example.com/notebook?file=test.py",
        hash: "",
      },
      writable: true,
    });
  });

  afterEach(() => {
    // Restore original location
    Object.defineProperty(window, "location", {
      value: originalLocation,
      writable: true,
    });
  });

  describe("createCellLink", () => {
    it("should create a URL with the cell name in the hash", () => {
      const url = createCellLink("myCellName");
      expect(url).toBe(
        "https://example.com/notebook?file=test.py#scrollTo=myCellName",
      );
    });

    it("should encode special characters in cell name", () => {
      const url = createCellLink("cell name with spaces & symbols");
      expect(url).toBe(
        "https://example.com/notebook?file=test.py#scrollTo=cell%20name%20with%20spaces%20%26%20symbols",
      );
    });
  });

  describe("extractCellNameFromHash", () => {
    it("should extract cell name from hash", () => {
      expect(extractCellNameFromHash("#scrollTo=cell1")).toBe("cell1");
      expect(extractCellNameFromHash("#scrollTo=cell1&other=param")).toBe(
        "cell1",
      );
      expect(extractCellNameFromHash("#other=param&scrollTo=cell1")).toBe(
        "cell1",
      );
    });

    it("should return null if no cell name is found", () => {
      expect(extractCellNameFromHash("")).toBeNull();
      expect(extractCellNameFromHash("#other=param")).toBeNull();
    });

    it("should decode special characters in cell name", () => {
      const cellName = extractCellNameFromHash(
        "#scrollTo=cell%20name%20with%20spaces%20%26%20symbols",
      );
      expect(cellName).toBe("cell name with spaces & symbols");
    });
  });

  describe("canLinkToCell", () => {
    it("should return true for valid cell name", () => {
      expect(canLinkToCell("myCellName")).toBe(true);
    });

    it("should return false for empty cell name", () => {
      expect(canLinkToCell("")).toBe(false);
    });

    it("should return false for undefined cell name", () => {
      expect(canLinkToCell(undefined)).toBe(false);
    });

    it("should return false for whitespace-only cell name", () => {
      expect(canLinkToCell("   ")).toBe(false);
    });

    it("should return false for default cell name", () => {
      expect(canLinkToCell("_")).toBe(false);
    });
  });

  describe("edge case cell names with unicode and special characters", () => {
    it.each(EDGE_CASE_CELL_NAMES)(
      "should handle unicode cell names in createCellLink: %s",
      (cellName) => {
        const url = createCellLink(cellName);
        expect(url).toContain("scrollTo=");
        expect(url).toContain(encodeURIComponent(cellName));
      },
    );

    it.each(EDGE_CASE_CELL_NAMES)(
      "should round-trip unicode cell names correctly: %s",
      (cellName) => {
        const url = createCellLink(cellName);
        const hash = url.split("#")[1];
        const extracted = extractCellNameFromHash(`#${hash}`);
        expect(extracted).toBe(cellName);
      },
    );

    it.each(EDGE_CASE_CELL_NAMES)(
      "should allow linking to unicode cell names: %s",
      (cellName) => {
        expect(canLinkToCell(cellName)).toBe(true);
      },
    );
  });
});
