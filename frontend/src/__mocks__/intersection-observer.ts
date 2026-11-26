/* Copyright 2026 Marimo. All rights reserved. */
import { vi } from "vitest";

export function mockIntersectionObservers() {
  const observers: ReturnType<typeof createObserver>[] = [];
  function createObserver(callback: IntersectionObserverCallback) {
    const observer = {
      root: null,
      rootMargin: "0px",
      scrollMargin: "0px",
      thresholds: [0],
      observe: vi.fn(),
      unobserve: vi.fn(),
      disconnect: vi.fn(),
      takeRecords: () => [],
      emit(target: Element, visible: boolean) {
        const rect = new DOMRect();
        callback(
          [
            {
              target,
              isIntersecting: visible,
              intersectionRatio: visible ? 1 : 0,
              time: 0,
              boundingClientRect: rect,
              intersectionRect: rect,
              rootBounds: rect,
            },
          ],
          observer,
        );
      },
    };
    return observer;
  }
  vi.stubGlobal(
    "IntersectionObserver",
    vi.fn(function (callback: IntersectionObserverCallback) {
      const observer = createObserver(callback);
      observers.push(observer);
      return observer;
    }),
  );
  return observers;
}
