/* Copyright 2026 Marimo. All rights reserved. */

import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  shouldShowScrollHint,
  SlideScrollContainer,
} from "../slide-scroll-hint";

describe("shouldShowScrollHint", () => {
  it("shows when content overflows and scroll is at the top", () => {
    expect(
      shouldShowScrollHint({
        scrollHeight: 800,
        clientHeight: 400,
        scrollTop: 0,
      }),
    ).toBe(true);
  });

  it("hides when content fits", () => {
    expect(
      shouldShowScrollHint({
        scrollHeight: 300,
        clientHeight: 400,
        scrollTop: 0,
      }),
    ).toBe(false);
  });

  it("hides after the user scrolls down", () => {
    expect(
      shouldShowScrollHint({
        scrollHeight: 800,
        clientHeight: 400,
        scrollTop: 40,
      }),
    ).toBe(false);
  });

  it("ignores sub-pixel overflow", () => {
    expect(
      shouldShowScrollHint({
        scrollHeight: 401,
        clientHeight: 400,
        scrollTop: 0,
      }),
    ).toBe(false);
  });

  it("still shows within the top threshold", () => {
    expect(
      shouldShowScrollHint({
        scrollHeight: 800,
        clientHeight: 400,
        scrollTop: 8,
      }),
    ).toBe(true);
  });
});

describe("SlideScrollContainer", () => {
  const resizeObservers: Array<{
    callback: ResizeObserverCallback;
    observe: ReturnType<typeof vi.fn>;
    disconnect: ReturnType<typeof vi.fn>;
  }> = [];

  beforeEach(() => {
    resizeObservers.length = 0;
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      cb(0);
      return 0;
    });
    vi.stubGlobal("cancelAnimationFrame", vi.fn());
    global.ResizeObserver = class MockResizeObserver {
      callback: ResizeObserverCallback;
      observe = vi.fn();
      unobserve = vi.fn();
      disconnect = vi.fn();

      constructor(callback: ResizeObserverCallback) {
        this.callback = callback;
        resizeObservers.push(this);
      }
    } as unknown as typeof ResizeObserver;

    global.MutationObserver = class MockMutationObserver {
      observe = vi.fn();
      disconnect = vi.fn();
      takeRecords = vi.fn(() => []);
    } as unknown as typeof MutationObserver;
  });

  function stubOverflow(
    el: HTMLElement,
    metrics: {
      scrollHeight: number;
      clientHeight: number;
      scrollTop?: number;
    },
  ) {
    Object.defineProperty(el, "scrollHeight", {
      configurable: true,
      get: () => metrics.scrollHeight,
    });
    Object.defineProperty(el, "clientHeight", {
      configurable: true,
      get: () => metrics.clientHeight,
    });
    Object.defineProperty(el, "scrollTop", {
      configurable: true,
      get: () => metrics.scrollTop ?? 0,
      set: (value: number) => {
        metrics.scrollTop = value;
      },
    });
  }

  it("renders a scroll hint when content overflows", () => {
    render(
      <SlideScrollContainer>
        <div>tall content</div>
      </SlideScrollContainer>,
    );

    const container = screen.getByTestId("slide-scroll-container");
    stubOverflow(container, { scrollHeight: 900, clientHeight: 400 });

    act(() => {
      for (const observer of resizeObservers) {
        observer.callback([], observer as unknown as ResizeObserver);
      }
    });

    expect(screen.getByTestId("slide-scroll-hint")).toBeTruthy();
    expect(screen.getByText("Scroll for more")).toBeTruthy();
  });

  it("hides the hint after scrolling", () => {
    const metrics = {
      scrollHeight: 900,
      clientHeight: 400,
      scrollTop: 0,
    };

    render(
      <SlideScrollContainer>
        <div>tall content</div>
      </SlideScrollContainer>,
    );

    const container = screen.getByTestId("slide-scroll-container");
    stubOverflow(container, metrics);

    act(() => {
      for (const observer of resizeObservers) {
        observer.callback([], observer as unknown as ResizeObserver);
      }
    });
    expect(screen.getByTestId("slide-scroll-hint")).toBeTruthy();

    act(() => {
      metrics.scrollTop = 50;
      container.dispatchEvent(new Event("scroll"));
    });

    expect(screen.queryByTestId("slide-scroll-hint")).toBeNull();
  });

  it("does not show a hint when content fits", () => {
    render(
      <SlideScrollContainer>
        <div>short content</div>
      </SlideScrollContainer>,
    );

    const container = screen.getByTestId("slide-scroll-container");
    stubOverflow(container, { scrollHeight: 200, clientHeight: 400 });

    act(() => {
      for (const observer of resizeObservers) {
        observer.callback([], observer as unknown as ResizeObserver);
      }
    });

    expect(screen.queryByTestId("slide-scroll-hint")).toBeNull();
  });
});
