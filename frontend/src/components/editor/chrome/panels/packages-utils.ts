/* Copyright 2024 Marimo. All rights reserved. */
import { atom } from "jotai";
import type { PanelType } from "../types";

// Atom to store the packages to prefill in the packages panel
export const packagesToInstallAtom = atom<string | null>(null);

export const PACKAGES_INPUT_ID = "packages-install-input";

export const focusPackagesInput = () => {
  requestAnimationFrame(() => {
    const input = document.getElementById(PACKAGES_INPUT_ID);
    if (input) {
      input.focus();
    }
  });
};

interface ChromeActions {
  openApplication: (panel: PanelType) => void;
}

export const openPackageManager = (chromeActions: ChromeActions) => {
  chromeActions.openApplication("packages");
  focusPackagesInput();
};
