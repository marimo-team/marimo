/* Copyright 2026 Marimo. All rights reserved. */

import type { RefObject } from "react";
import { useEffect, useState } from "react";

/**
 * Hook to detect if an element's content overflows its visible area.
 * Uses ResizeObserver to track size changes.
 *
 * @param ref - Ref to the element to observe
 * @param enabled - When this changes, re-setup the observer (use to handle element recreation)
 */
export function useOverflowDetection(
  ref: RefObject<HTMLElement | null>,
  enabled = true,
): boolean {
  const [isOverflowing, setIsOverflowing] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || !enabled) {
      return;
    }

    const resizeObserver = new ResizeObserver(() => {
      setIsOverflowing(el.scrollHeight > el.clientHeight);
    });
    resizeObserver.observe(el);

    return () => {
      resizeObserver.disconnect();
    };
  }, [ref, enabled]);

  return isOverflowing;
}
