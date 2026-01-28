/* Copyright 2026 Marimo. All rights reserved. */
import { atom, useAtomValue } from "jotai";
import { useMemo } from "react";
import { resolvedMarimoConfigAtom } from "./config";
import type { PanelDescriptor } from "@/components/editor/chrome/types";
import { isPanelHidden } from "@/components/editor/chrome/types";
import type { Capabilities } from "@/core/kernel/messages";

// Types
export interface EmbeddingPanelConfig {
  files?: boolean;
  variables?: boolean;
  packages?: boolean;
  ai?: boolean;
  outline?: boolean;
  documentation?: boolean;
  dependencies?: boolean;
  snippets?: boolean;
  errors?: boolean;
  scratchpad?: boolean;
  tracing?: boolean;
  secrets?: boolean;
  logs?: boolean;
  terminal?: boolean;
  cache?: boolean;
}

export interface EmbeddingFeaturesConfig {
  settings?: boolean;
  sharing?: boolean;
  feedback?: boolean;
  command_palette?: boolean;
  app_config?: boolean;
  keyboard_shortcuts?: boolean;
}

export interface EmbeddingConfig {
  enabled?: boolean;
  panels?: EmbeddingPanelConfig;
  features?: EmbeddingFeaturesConfig;
}

// Atoms
export const embeddingConfigAtom = atom<EmbeddingConfig | undefined>((get) => {
  return get(resolvedMarimoConfigAtom).server?.embedding;
});

export const isEmbeddingModeAtom = atom<boolean>((get) => {
  return get(embeddingConfigAtom)?.enabled ?? false;
});

/**
 * Hook: Filter panels with embedding logic ON TOP of existing isPanelHidden.
 * Does NOT modify isPanelHidden - just wraps it with an additional filter.
 *
 * When embedding mode is enabled, panels are hidden by default unless
 * explicitly enabled in the embedding config.
 */
export function useEmbeddingFilteredPanels(
  panels: PanelDescriptor[],
  capabilities: Capabilities,
): PanelDescriptor[] {
  const embeddingConfig = useAtomValue(embeddingConfigAtom);

  return useMemo(() => {
    return panels.filter((panel) => {
      // First: apply existing upstream logic (unchanged)
      if (isPanelHidden(panel, capabilities)) {
        return false;
      }
      // Then: apply embedding filter (additive)
      if (embeddingConfig?.enabled) {
        // In embedding mode, panels are hidden unless explicitly enabled
        return embeddingConfig.panels?.[panel.type] === true;
      }
      return true;
    });
  }, [panels, capabilities, embeddingConfig]);
}

/**
 * Hook: Check if a feature is enabled in embedding mode.
 *
 * When not in embedding mode, all features are enabled.
 * When in embedding mode, features are disabled unless explicitly enabled.
 */
export function useEmbeddingFeature(
  feature: keyof EmbeddingFeaturesConfig,
): boolean {
  const embeddingConfig = useAtomValue(embeddingConfigAtom);

  if (!embeddingConfig?.enabled) {
    return true; // Not in embedding mode, all features enabled
  }
  return embeddingConfig.features?.[feature] === true;
}
