/* Copyright 2026 Marimo. All rights reserved. */

import { type RefObject, useEffect } from "react";

/**
 * Vega-Lite's width:"container" only remeasures on window.resize — not when a
 * parent goes from display:none / zero-size to a real layout size. Observe the
 * embed host and dispatch the event Vega already listens for when the container
 * gains a positive width.
 */
export function useVegaContainerRemeasure(
  ref: RefObject<HTMLElement | null>,
  enabled: boolean,
): void {
  useEffect(() => {
    const el = ref.current;
    if (!el || !enabled || typeof ResizeObserver === "undefined") {
      return;
    }

    let lastWidth = el.clientWidth;
    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width ?? 0;
      if (width <= 0) {
        lastWidth = 0;
        return;
      }
      if (Math.round(width) === Math.round(lastWidth)) {
        return;
      }
      lastWidth = width;
      requestAnimationFrame(() => {
        window.dispatchEvent(new Event("resize"));
      });
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref, enabled]);
}
