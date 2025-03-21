/* Copyright 2024 Marimo. All rights reserved. */
import type {
  CompletionConfig,
  DiagnosticsConfig,
  LSPConfig,
} from "@/core/config/config-schema";
import type { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import type { CellId } from "@/core/cells/ids";
import { singleFacet } from "../facet";
import { diagnosticsEnabled } from "@marimo-team/codemirror-languageserver";

/**
 * State for completion config
 */
export const completionConfigState = singleFacet<CompletionConfig>();

/**
 * State for hotkeys provider
 */
export const hotkeysProviderState = singleFacet<HotkeyProvider>();

export type PlaceholderType = "marimo-import" | "ai" | "none";
/**
 * State for placeholder type
 */
export const placeholderState = singleFacet<PlaceholderType>();

/**
 * State for cell id
 */
export const cellIdState = singleFacet<CellId>();

/**
 * State for LSP config
 */
export const lspConfigState = singleFacet<LSPConfig>();

/**
 * State for diagnostics config
 */
export const diagnosticsConfigState = singleFacet<DiagnosticsConfig>();

/**
 * Extension for cell config
 */
export function cellConfigExtension(
  completionConfig: CompletionConfig,
  hotkeys: HotkeyProvider,
  placeholderType: PlaceholderType,
  lspConfig: LSPConfig,
  diagnosticsConfig: DiagnosticsConfig,
) {
  return [
    // Store state
    completionConfigState.of(completionConfig),
    hotkeysProviderState.of(hotkeys),
    placeholderState.of(placeholderType),
    lspConfigState.of(lspConfig),
    diagnosticsConfigState.of(diagnosticsConfig),
    // Enable diagnostics (default to false)
    diagnosticsEnabled.of(diagnosticsConfig?.enabled ?? false),
  ];
}
