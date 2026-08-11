/* Copyright 2026 Marimo. All rights reserved. */
import { componentRenderCountAtom, profilingEnabledAtom } from "./atoms";
import { store } from "@/core/state/jotai";

export function useProfiling(componentName: string): void {
  if (!store.get(profilingEnabledAtom)) {
    return;
  }

  store.set(componentRenderCountAtom, (prev) => ({
    ...prev,
    [componentName]: (prev[componentName] ?? 0) + 1,
  }));
}
