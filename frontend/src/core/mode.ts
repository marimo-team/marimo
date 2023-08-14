/* Copyright 2023 Marimo. All rights reserved. */
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
