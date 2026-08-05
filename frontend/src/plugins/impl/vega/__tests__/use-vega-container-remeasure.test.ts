/* Copyright 2026 Marimo. All rights reserved. */

import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useRef } from "react";
import { useVegaContainerRemeasure } from "../use-vega-container-remeasure";

describe("useVegaContainerRemeasure", () => {
  let observers: FakeResizeObserver[];
  let OriginalResizeObserver: typeof ResizeObserver;

  class FakeResizeObserver {
    callback: ResizeObserverCallback;
    el: Element | null = null;

    constructor(callback: ResizeObserverCallback) {
      this.callback = callback;
      observers.push(this);
    }

    observe(el: Element) {
      this.el = el;
    }

    disconnect() {
      this.el = null;
    }

    unobserve() {
      this.el = null;
    }

    trigger(width: number) {
      this.callback(
        [
          {
            target: this.el!,
            contentRect: {
              width,
              height: 100,
              x: 0,
              y: 0,
              top: 0,
              left: 0,
              bottom: 100,
              right: width,
              toJSON: () => ({}),
            },
            borderBoxSize: [],
            contentBoxSize: [],
            devicePixelContentBoxSize: [],
          } satisfies ResizeObserverEntry,
        ],
        this,
      );
    }
  }

  beforeEach(() => {
    observers = [];
    OriginalResizeObserver = globalThis.ResizeObserver;
    globalThis.ResizeObserver =
      FakeResizeObserver as unknown as typeof ResizeObserver;
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      cb(0);
      return 0;
    });
  });

  afterEach(() => {
    globalThis.ResizeObserver = OriginalResizeObserver;
    vi.unstubAllGlobals();
  });

  it("dispatches window resize when the container gains width", () => {
    const el = document.createElement("div");
    Object.defineProperty(el, "clientWidth", { value: 0, configurable: true });
    const dispatchSpy = vi.spyOn(window, "dispatchEvent");

    renderHook(() => {
      const ref = useRef<HTMLDivElement>(el);
      useVegaContainerRemeasure(ref, true);
    });

    expect(observers).toHaveLength(1);
    observers[0].trigger(0);
    expect(dispatchSpy).not.toHaveBeenCalled();

    observers[0].trigger(640);
    expect(dispatchSpy).toHaveBeenCalledWith(expect.any(Event));
    expect(dispatchSpy.mock.calls[0][0].type).toBe("resize");
  });

  it("is a no-op when disabled", () => {
    const el = document.createElement("div");
    renderHook(() => {
      const ref = useRef<HTMLDivElement>(el);
      useVegaContainerRemeasure(ref, false);
    });
    expect(observers).toHaveLength(0);
  });
});
