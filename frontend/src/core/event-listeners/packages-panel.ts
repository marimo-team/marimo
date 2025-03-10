/* Copyright 2024 Marimo. All rights reserved. */
import { store } from "@/core/state/jotai";
import { chromeAtom } from "@/components/editor/chrome/state";
import { PACKAGES_INPUT_ID } from "@/components/editor/chrome/panels/constants";

/**
 * Event handler for opening the packages panel
 */
export function handleOpenPackagesPanel(): void {
  // Open the packages panel
  store.set(chromeAtom, (prev) => ({
    ...prev,
    isSidebarOpen: true,
    selectedPanel: "packages",
  }));

  // Focus the packages input
  requestAnimationFrame(() => {
    const input = document.getElementById(PACKAGES_INPUT_ID);
    if (input) {
      input.focus();
    }
  });
}

/**
 * Initialize event listener for opening the packages panel
 * This is called directly in plugins.ts
 */
export function initPackagesPanelEventListener(): void {
  document.addEventListener(
    "marimo:open-packages-panel",
    handleOpenPackagesPanel,
  );
}
