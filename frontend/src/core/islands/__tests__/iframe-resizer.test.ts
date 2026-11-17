/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { registerIframeResizer } from "../iframe-resizer";

const observe = vi.fn();
let notifyResize: () => void = vi.fn();

beforeEach(() => {
  delete window.__resizeIframe;
  document.body.replaceChildren();
  vi.stubGlobal(
    "ResizeObserver",
    class {
      public constructor(callback: () => void) {
        notifyResize = callback;
      }
      public observe = observe;
    },
  );
  registerIframeResizer();
});

afterEach(() => {
  delete window.__resizeIframe;
  vi.unstubAllGlobals();
});

function createIframe() {
  const iframe = document.createElement("iframe");
  document.body.append(iframe);
  const element = iframe.contentDocument!.documentElement;
  Object.defineProperties(element, {
    scrollHeight: { configurable: true, value: 600 },
    clientHeight: { configurable: true, value: 150 },
    scrollWidth: { configurable: true, value: 300 },
    clientWidth: { configurable: true, value: 300 },
  });
  return { iframe, element };
}

describe("islands iframe resizing", () => {
  it("resizes overflowing content and observes subsequent height changes", () => {
    const { iframe, element } = createIframe();

    window.__resizeIframe!(iframe);

    expect(iframe.style.height).toBe("600px");
    expect(observe).toHaveBeenCalledExactlyOnceWith(
      iframe.contentDocument!.body,
    );

    Object.defineProperty(element, "scrollHeight", { value: 900 });
    notifyResize();
    expect(iframe.style.height).toBe("900px");
  });

  it("allows space for a horizontal scrollbar", () => {
    const { iframe, element } = createIframe();
    Object.defineProperty(element, "scrollWidth", { value: 500 });

    window.__resizeIframe!(iframe);

    expect(iframe.style.height).toBe("620px");
  });

  it("preserves the height when there is no vertical overflow", () => {
    const { iframe, element } = createIframe();
    Object.defineProperty(element, "scrollHeight", { value: 150 });
    iframe.style.height = "150px";

    window.__resizeIframe!(iframe);

    expect(iframe.style.height).toBe("150px");
  });

  it("ignores an iframe whose content window is not ready", () => {
    const iframe = document.createElement("iframe");

    expect(() => window.__resizeIframe!(iframe)).not.toThrow();
    expect(observe).not.toHaveBeenCalled();
  });

  it("keeps the same handler across repeated registration", () => {
    const handler = window.__resizeIframe;

    registerIframeResizer();

    expect(window.__resizeIframe).toBe(handler);
  });
});
