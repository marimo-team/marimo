/* Copyright 2026 Marimo. All rights reserved. */
import { useEffect, type RefObject } from "react";
import type { createSharedIntersectionObserver } from "@/utils/shared-intersection-observer";

/** Disabling or disposing a subscription reports that the target is no longer observed. */
export function useSharedIntersectionObserver(
  target: RefObject<Element | null>,
  subscribe: ReturnType<typeof createSharedIntersectionObserver>,
  onChange: (visible: boolean) => void,
  enabled = true,
) {
  useEffect(() => {
    if (!enabled || !target.current) {
      return;
    }
    const release = subscribe(target.current, onChange);
    return () => {
      release();
      onChange(false);
    };
  }, [target, subscribe, onChange, enabled]);
}
