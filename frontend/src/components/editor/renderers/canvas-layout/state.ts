/* Copyright 2024 Marimo. All rights reserved. */

import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { jotaiJsonStorage } from "@/utils/storage/jotai";
import type { CanvasSettings, CanvasViewport } from "./models";

/**
 * Default canvas settings
 */
export const DEFAULT_CANVAS_SETTINGS: CanvasSettings = {
  gridSize: 20,
  snapToGrid: true,
  showMinimap: false,
  dataFlow: "left-right",
  interactionMode: "pointer",
  debug: false,
};

/**
 * Default viewport
 */
export const DEFAULT_VIEWPORT: CanvasViewport = {
  x: 0,
  y: 0,
  zoom: 1,
};

/**
 * Canvas settings atom with localStorage persistence
 */
export const canvasSettingsAtom = atomWithStorage<CanvasSettings>(
  "marimo:canvas-settings",
  DEFAULT_CANVAS_SETTINGS,
  jotaiJsonStorage,
);

/**
 * Canvas viewport atom
 */
export const canvasViewportAtom = atom<CanvasViewport>(DEFAULT_VIEWPORT);

/**
 * AI prompt state for canvas layout
 */
export interface CanvasAIPromptState {
  isOpen: boolean;
  prompt: string;
}

/**
 * Default AI prompt state
 */
export const DEFAULT_AI_PROMPT_STATE: CanvasAIPromptState = {
  isOpen: false,
  prompt: "",
};

/**
 * Canvas AI prompt atom (not persisted)
 */
export const canvasAIPromptAtom = atom<CanvasAIPromptState>(
  DEFAULT_AI_PROMPT_STATE,
);
