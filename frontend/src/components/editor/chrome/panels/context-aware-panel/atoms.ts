/* Copyright 2024 Marimo. All rights reserved. */

import { atom } from "jotai";

/**
 * Unique ID of the owner rendering the context-aware panel.
 */
export const contextAwarePanelOwner = atom<string | null>(null);

/**
 * If true, the panel is open.
 */
export const contextAwarePanelOpen = atom<boolean>(false);

/**
 * If true, the panel is treated as part of the editor.
 * When false, the panel overlays the editor content.
 */
export const isPinnedAtom = atom<boolean>(false);

/**
 * If true, the panel is cell-aware and will switch content based on the focused cell.
 * Else, user needs to manually trigger content switch.
 */
export const isCellAwareAtom = atom<boolean>(false);
