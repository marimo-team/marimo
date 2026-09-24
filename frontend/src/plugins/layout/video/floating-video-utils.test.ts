/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import {
  type FloatingCorner,
  getCornerPosition,
  getFloatingViewportBounds,
} from "./floating-video-utils";

describe("floating video safe area", () => {
  const originalInnerWidth = window.innerWidth;
  const originalInnerHeight = window.innerHeight;
  const chromeElements: HTMLElement[] = [];

  beforeEach(() => {
    setViewport(1200, 800);
    chromeElements.push(
      appendAppElement(rect({ left: 64, top: 0, width: 1136, height: 760 })),
      appendChromeElement(
        "chrome-controls-top-right",
        rect({ left: 1080, top: 12, width: 104, height: 32 }),
      ),
      appendChromeElement(
        "chrome-controls-bottom-right",
        rect({ left: 1120, top: 560, width: 64, height: 184 }),
      ),
    );
  });

  afterEach(() => {
    for (const element of chromeElements.splice(0)) {
      element.remove();
    }
    setViewport(originalInnerWidth, originalInnerHeight);
    vi.restoreAllMocks();
  });

  test.each<[FloatingCorner, { x: number; y: number }]>([
    ["top-left", { x: 80, y: 16 }],
    ["top-right", { x: 704, y: 16 }],
    ["bottom-left", { x: 80, y: 541.5 }],
    ["bottom-right", { x: 704, y: 541.5 }],
  ])("positions %s clear of notebook chrome", (corner, expected) => {
    const bounds = getFloatingViewportBounds();

    expect(bounds).toEqual({ left: 64, top: 0, right: 1080, bottom: 760 });
    expect(
      getCornerPosition(corner, { width: 360, height: 202.5 }, bounds),
    ).toEqual(expected);
  });
});

const appendAppElement = (bounds: DOMRect): HTMLElement => {
  const element = document.createElement("div");
  element.id = "App";
  vi.spyOn(element, "getBoundingClientRect").mockReturnValue(bounds);
  document.body.append(element);
  return element;
};

const appendChromeElement = (id: string, bounds: DOMRect): HTMLElement => {
  const element = document.createElement("div");
  element.id = id;
  vi.spyOn(element, "getBoundingClientRect").mockReturnValue(bounds);
  document.body.append(element);
  return element;
};

const rect = ({
  left,
  top,
  width,
  height,
}: {
  left: number;
  top: number;
  width: number;
  height: number;
}): DOMRect =>
  ({
    left,
    top,
    width,
    height,
    right: left + width,
    bottom: top + height,
    x: left,
    y: top,
    toJSON: () => ({}),
  }) as DOMRect;

const setViewport = (width: number, height: number) => {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    value: width,
  });
  Object.defineProperty(window, "innerHeight", {
    configurable: true,
    value: height,
  });
};
