/* Copyright 2026 Marimo. All rights reserved. */

import { atom, useAtom, useSetAtom } from "jotai";

export const dependencyPanelTabAtom = atom<"minimap" | "graph">("minimap");

export function useDependencyPanelTab() {
  const [dependencyPanelTab, setDependencyPanelTab] = useAtom(
    dependencyPanelTabAtom,
  );
  return { dependencyPanelTab, setDependencyPanelTab };
}

export function useSetDependencyPanelTab() {
  return useSetAtom(dependencyPanelTabAtom);
}
