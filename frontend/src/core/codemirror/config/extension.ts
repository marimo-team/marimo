/* Copyright 2024 Marimo. All rights reserved. */
import { CompletionConfig } from "@/core/config/config-schema";
import { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import { Facet } from "@codemirror/state";
import { MovementCallbacks } from "../cells/extensions";

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
