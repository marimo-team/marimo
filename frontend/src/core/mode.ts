/* Copyright 2024 Marimo. All rights reserved. */

import { atom } from "jotai";
import { CellId } from "./cells/ids";
import { store } from "./state/jotai";

/**
 * This is the internal mode.
 * - `read`: A user is reading the notebook. Cannot switch to edit/present mode.
 * - `edit`: A user is editing the notebook. Can switch to present mode.
 * - `present`: A user is presenting the notebook, it looks like read mode but with some editing features. Cannot switch to present mode.
 */
export type AppMode = "read" | "edit" | "present";

export function getInitialAppMode(): AppMode {
  const tag = document.querySelector("marimo-mode");
  if (tag === null || !(tag instanceof HTMLElement)) {
    throw new Error("internal-error: marimo-mode tag not found");
  }

  const mode = tag.dataset.mode;
  switch (mode) {
    case "read":
      return "read";
    case "edit":
      return "edit";
    default:
      // We can only start in 'read' or 'edit' mode.
      throw new Error(`internal-error: unknown mode ${mode}`);
  }
}

export function toggleAppMode(mode: AppMode): AppMode {
  // Can't switch to present mode.
  if (mode === "read") {
    return "read";
  }

  return mode === "edit" ? "present" : "edit";
}

/**
 * View state for the app.
 */
interface ViewState {
  /**
   * The mode of the app: read/edit/present
   */
  mode: AppMode;
  /**
   * A cell ID to anchor scrolling to when toggling between presenting and
   * editing views
   */
  cellAnchor: CellId | null;
}

export const initialMode = getInitialAppMode();

export async function runDuringPresentMode(
  fn: () => void | Promise<void>,
): Promise<void> {
  const state = store.get(viewStateAtom);
  if (state.mode === "present") {
    await fn();
    return;
  }

  store.set(viewStateAtom, { ...state, mode: "present" });
  // Wait 100ms to allow the page to render
  await new Promise((resolve) => setTimeout(resolve, 100));
  // Wait 2 frames
  await new Promise((resolve) => requestAnimationFrame(resolve));
  await new Promise((resolve) => requestAnimationFrame(resolve));
  await fn();
  store.set(viewStateAtom, { ...state, mode: "edit" });
  return undefined;
}

export const viewStateAtom = atom<ViewState>({
  mode: initialMode,
  cellAnchor: null,
});
