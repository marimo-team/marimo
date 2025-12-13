/* Copyright 2024 Marimo. All rights reserved. */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { smartScrollIntoView } from "../scroll";

describe("smartScrollIntoView", () => {
  let element: HTMLElement;
  let mockScrollBy: ReturnType<typeof vi.fn>;

  const mockRect = (top: number, bottom: number): DOMRect => ({
    top,
    bottom,
    left: 0,
    right: 100,
    width: 100,
    height: 100,
    x: 0,
    y: top,
    toJSON: () => ({}),
  });

  beforeEach(() => {
    element = document.createElement("div");
    document.body.append(element);

    mockScrollBy = vi.fn();
    window.scrollBy = mockScrollBy;

    Object.defineProperty(window, "innerHeight", {
      writable: true,
      configurable: true,
      value: 1000,
    });
  });

  it("should scroll when element is above viewport", () => {
    vi.spyOn(element, "getBoundingClientRect").mockReturnValue(
      mockRect(-50, 50),
    );

    smartScrollIntoView(element, {
      offset: { top: 10, bottom: 20 },
    });

    expect(mockScrollBy).toHaveBeenCalledWith({
      top: -60,
      behavior: "smooth",
    });
  });

  it("should scroll when element is below viewport", () => {
    vi.spyOn(element, "getBoundingClientRect").mockReturnValue(
      mockRect(950, 1050),
    );

    smartScrollIntoView(element, {
      offset: { top: 10, bottom: 20 },
    });

    expect(mockScrollBy).toHaveBeenCalledWith({
      top: 70,
      behavior: "smooth",
    });
  });

  it("should not scroll when element is in view", () => {
    vi.spyOn(element, "getBoundingClientRect").mockReturnValue(
      mockRect(100, 200),
    );

    smartScrollIntoView(element, {
      offset: { top: 10, bottom: 20 },
    });

    expect(mockScrollBy).not.toHaveBeenCalled();
  });

  it("should respect behavior parameter", () => {
    vi.spyOn(element, "getBoundingClientRect").mockReturnValue(
      mockRect(-50, 50),
    );

    smartScrollIntoView(element, {
      offset: { top: 10, bottom: 20 },
      behavior: "instant",
    });

    expect(mockScrollBy).toHaveBeenCalledWith({
      top: -60,
      behavior: "instant",
    });
  });

  it("should scroll custom body element", () => {
    const customBody = document.createElement("div");
    const mockCustomScrollBy = vi.fn();
    customBody.scrollBy = mockCustomScrollBy;

    vi.spyOn(element, "getBoundingClientRect").mockReturnValue(
      mockRect(-50, 50),
    );

    smartScrollIntoView(element, {
      offset: { top: 10, bottom: 20 },
      body: customBody,
    });

    expect(mockCustomScrollBy).toHaveBeenCalledWith({
      top: -60,
      behavior: "smooth",
    });
    expect(mockScrollBy).not.toHaveBeenCalled();
  });
});
