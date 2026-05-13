/* Copyright 2026 Marimo. All rights reserved. */
/* oxlint-disable typescript/no-empty-object-type */

import type { CellId } from "@/core/cells/ids";

/**
 * The serialized form of a slides layout.
 * This must be backwards-compatible as it is stored on the user's disk.
 */
// oxlint-disable-next-line typescript/consistent-type-definitions
export type SerializedSlidesLayout = {
  // Both fields are optional so files saved before these existed (e.g. the
  // bare `{}` emitted by earlier marimo versions) still deserialize cleanly.
  deck?: DeckConfig;
  cells?: SlideConfig[];
};

export interface SlidesLayout extends Omit<
  SerializedSlidesLayout,
  "cells" | "deck"
> {
  // We map the cells to their IDs so that we can track them as they move around.
  cells: Map<CellId, SlideConfig>;
  deck: DeckConfig;
}

export type SlideType = "slide" | "sub-slide" | "fragment" | "skip";
export interface SlideConfig {
  type?: SlideType;
}

export type DeckTransition =
  | "none"
  | "fade"
  | "slide"
  | "convex"
  | "concave"
  | "zoom";
export interface DeckConfig {
  transition?: DeckTransition;
}
