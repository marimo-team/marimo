/* Copyright 2024 Marimo. All rights reserved. */

import type { CellId } from "@/core/cells/ids";
import type {
  CompletionConfig,
  DiagnosticsConfig,
  LSPConfig,
} from "@/core/config/config-schema";
import type { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import { singleFacet } from "../facet";
import type { PlaceholderType } from "./types";

/**
 * State for completion config
 */
export const completionConfigState = singleFacet<CompletionConfig>();

/**
 * State for hotkeys provider
 */
export const hotkeysProviderState = singleFacet<HotkeyProvider>();

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
export const lspConfigState = singleFacet<
  LSPConfig & { diagnostics: DiagnosticsConfig }
>();

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
    lspConfigState.of({ ...lspConfig, diagnostics: diagnosticsConfig }),
  ];
}
