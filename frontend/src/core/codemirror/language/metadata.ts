/* Copyright 2024 Marimo. All rights reserved. */
import { StateField, StateEffect, type EditorState } from "@codemirror/state";
import type { EditorView } from "@codemirror/view";

/**
 * Metadata for language adapters
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type LanguageMetadata = Record<string, any>;

/**
 * Effect to set language metadata
 */
export const setLanguageMetadata = StateEffect.define<LanguageMetadata>();

/**
 * Effect to update language metadata (partial update)
 */
export const updateLanguageMetadata =
  StateEffect.define<Partial<LanguageMetadata>>();

/**
 * State field for language metadata
 */
export const languageMetadataField = StateField.define<LanguageMetadata>({
  create: () => ({}),
  update: (value, tr) => {
    for (const effect of tr.effects) {
      if (effect.is(setLanguageMetadata)) {
        return effect.value;
      }
      if (effect.is(updateLanguageMetadata)) {
        return { ...value, ...effect.value };
      }
    }
    return value;
  },
});

/**
 * Get language metadata from editor state
 */
export function getLanguageMetadata(state: EditorState): LanguageMetadata {
  return state.field(languageMetadataField);
}

/**
 * Set language metadata in editor view
 */
export function setLanguageMetadataCommand(
  view: EditorView,
  metadata: LanguageMetadata,
): boolean {
  view.dispatch({
    effects: setLanguageMetadata.of(metadata),
  });
  return true;
}

/**
 * Update language metadata in editor view (partial update)
 */
export function updateLanguageMetadataCommand(
  view: EditorView,
  metadata: Partial<LanguageMetadata>,
): boolean {
  view.dispatch({
    effects: updateLanguageMetadata.of(metadata),
  });
  return true;
}
