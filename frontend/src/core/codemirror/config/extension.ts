/* Copyright 2024 Marimo. All rights reserved. */
import type { CompletionConfig, LSPConfig } from "@/core/config/config-schema";
import type { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import { Facet } from "@codemirror/state";
import type { CellId } from "@/core/cells/ids";

/**
 * State for completion config
 */
export const completionConfigState = Facet.define<
  CompletionConfig,
  CompletionConfig
>({
  combine: (values) => values[0],
});

/**
 * State for hotkeys provider
 */
export const hotkeysProviderState = Facet.define<
  HotkeyProvider,
  HotkeyProvider
>({
  combine: (values) => values[0],
});

/**
 * State for placeholder type
 */
export type PlaceholderType = "marimo-import" | "ai" | "none";
export const placeholderState = Facet.define<PlaceholderType, PlaceholderType>({
  combine: (values) => values[0],
});

/**
 * State for cell id
 */
export const cellIdState = Facet.define<CellId, CellId>({
  combine: (values) => values[0],
});

/**
 * State for LSP config
 */
export const lspConfigState = Facet.define<LSPConfig, LSPConfig>({
  combine: (values) => values[0],
});

/**
 * Extension for cell config
 */
export function cellConfigExtension(
  completionConfig: CompletionConfig,
  hotkeys: HotkeyProvider,
  placeholderType: PlaceholderType,
  lspConfig: LSPConfig,
) {
  return [
    // Store state
    completionConfigState.of(completionConfig),
    hotkeysProviderState.of(hotkeys),
    placeholderState.of(placeholderType),
    lspConfigState.of(lspConfig),
  ];
}
