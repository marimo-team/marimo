/* Copyright 2024 Marimo. All rights reserved. */

import type { EditorView } from "@codemirror/view";
import { languageAdapterState, switchLanguage } from "./extension";
import { LanguageAdapters } from "./LanguageAdapters";
import type { LanguageAdapterType } from "./types";
import { getEditorCodeAsPython } from "./utils";

/**
 * Get the current mode of the editor view.
 */
export function getCurrentLanguageAdapter(
  editorView: EditorView | null,
): LanguageAdapterType {
  if (!editorView) {
    return "python";
  }
  return editorView.state.field(languageAdapterState).type;
}

/**
 * Check if we can toggle to a given language
 */
function canToggleToLanguage(
  editorView: EditorView | null,
  language: LanguageAdapterType,
): boolean {
  // If there is no editor view or we are already in the language, return false
  if (!editorView || getCurrentLanguageAdapter(editorView) === language) {
    return false;
  }

  // If there is no code, we can always toggle to any language
  if (editorView.state.doc.toString().trim() === "") {
    return true;
  }

  return LanguageAdapters[language].isSupported(
    getEditorCodeAsPython(editorView),
  );
}

/**
 * Toggle to a given language
 */
export function toggleToLanguage(
  editorView: EditorView,
  language: LanguageAdapterType,
  opts: { force?: boolean } = {},
): LanguageAdapterType | false {
  // Check if the language can be toggled
  if (!opts.force && !canToggleToLanguage(editorView, language)) {
    return false;
  }

  switchLanguage(editorView, language);

  return language;
}
