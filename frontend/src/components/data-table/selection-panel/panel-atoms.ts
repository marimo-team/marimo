/* Copyright 2024 Marimo. All rights reserved. */
import type { CellId } from "@/core/cells/ids";
import { atom } from "jotai";

// Only one cell can be focused at a time
// So that we can close the selection panel when the focused cell changes
export const isCurrentlyFocusedCellAtom = atom<CellId | null>(null);

// Whether the selection panel is overlaid on top of the editor
export const isOverlayAtom = atom<boolean>(true);
