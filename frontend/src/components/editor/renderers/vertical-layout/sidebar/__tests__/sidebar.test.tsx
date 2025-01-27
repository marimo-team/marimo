import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import { Sidebar } from "../sidebar";
import { normalizeWidth } from "../state";

// Mock the react-slotz module
vi.mock("@marimo-team/react-slotz", () => ({
  useSlot: () => [],
  SlotzController: class {
    constructor() {}
    onComponentsChange() {}
    registerComponent() {}
    unregisterComponent() {}
  },
  Slot: () => null // Mock Slot component as a null-rendering component
}));

describe("Sidebar", () => {
  it("should use default width when no width is provided", () => {
    const { container } = render(
      <Sidebar isOpen={false} toggle={() => {}} />
    );
    const aside = container.querySelector("aside");
    expect(aside?.getAttribute("data-width")).toBe("288px");
    expect(aside?.style.width).toBe("68px"); // closed width when not open
  });

  it("should use provided width when width is specified", () => {
    const { container } = render(
      <Sidebar isOpen={true} toggle={() => {}} width="400px" />
    );
    const aside = container.querySelector("aside");
    expect(aside?.getAttribute("data-width")).toBe("400px");
    expect(aside?.style.width).toBe("400px"); // open width when isOpen is true
  });

  it("should convert numeric width to px", () => {
    const { container } = render(
      <Sidebar isOpen={true} toggle={() => {}} width="400" />
    );
    const aside = container.querySelector("aside");
    expect(aside?.getAttribute("data-width")).toBe("400px");
    expect(aside?.style.width).toBe("400px"); // open width when isOpen is true
  });
});

describe("normalizeWidth", () => {
  it("should return default width when no width is provided", () => {
    expect(normalizeWidth(undefined)).toBe("288px");
  });

  it("should add px to numeric values", () => {
    expect(normalizeWidth("400")).toBe("400px");
  });

  it("should not modify values with units", () => {
    expect(normalizeWidth("20rem")).toBe("20rem");
    expect(normalizeWidth("50%")).toBe("50%");
    expect(normalizeWidth("100vh")).toBe("100vh");
  });
});
