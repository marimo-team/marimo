/* Copyright 2024 Marimo. All rights reserved. */
import type { CompletionConfig } from "@/core/config/config-schema";
import type { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import { Facet } from "@codemirror/state";
import type { MovementCallbacks } from "../cells/extensions";
import type { CellId } from "@/core/cells/ids";

export const completionConfigState = Facet.define<
  CompletionConfig,
  CompletionConfig
>({
  combine: (values) => values[0],
});

export const hotkeysProviderState = Facet.define<
  HotkeyProvider,
  HotkeyProvider
>({
  combine: (values) => values[0],
});

export type PlaceholderType = "marimo-import" | "ai" | "none";
export const placeholderState = Facet.define<PlaceholderType, PlaceholderType>({
  combine: (values) => values[0],
});

export const movementCallbacksState = Facet.define<
  MovementCallbacks,
  MovementCallbacks
>({
  combine: (values) => values[0],
});

export const cellIdState = Facet.define<CellId, CellId>({
  combine: (values) => values[0],
});
