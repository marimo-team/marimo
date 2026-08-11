/* Copyright 2026 Marimo. All rights reserved. */
import {
  componentRenderCountAtom,
  editorViewCountAtom,
  profilingEnabledAtom,
  wsMessageCountAtom,
} from "./atoms";
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

export function incrementEditorViewCount(): void {
  if (!store.get(profilingEnabledAtom)) {
    return;
  }
  store.set(editorViewCountAtom, (prev) => prev + 1);
}

export function decrementEditorViewCount(): void {
  if (!store.get(profilingEnabledAtom)) {
    return;
  }
  store.set(editorViewCountAtom, (prev) => Math.max(0, prev - 1));
}

export function incrementWsMessageCount(): void {
  if (!store.get(profilingEnabledAtom)) {
    return;
  }
  store.set(wsMessageCountAtom, (prev) => prev + 1);
}
