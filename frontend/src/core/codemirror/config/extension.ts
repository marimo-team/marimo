/* Copyright 2024 Marimo. All rights reserved. */
import { CompletionConfig } from "@/core/config/config-schema";
import { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import { Facet } from "@codemirror/state";

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
