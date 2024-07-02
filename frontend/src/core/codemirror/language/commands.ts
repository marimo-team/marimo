/* Copyright 2024 Marimo. All rights reserved. */

import type { EditorView } from "@codemirror/view";
import { getEditorCodeAsPython } from "./utils";
import { languageAdapterState, switchLanguage } from "./extension";
import { LanguageAdapters } from "./LanguageAdapters";
import type { LanguageAdapterType } from "./types";

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
 *
 */
export function canToggleToLanguage(
  editorView: EditorView | null,
  language: LanguageAdapterType,
): boolean {
  if (!editorView || getCurrentLanguageAdapter(editorView) === language) {
    return false;
  }

  return LanguageAdapters[language]().isSupported(
    getEditorCodeAsPython(editorView),
  );
}

export function toggleToLanguage(
  editorView: EditorView,
  language: LanguageAdapterType,
): LanguageAdapterType | false {
  // Check if the language can be toggled
  if (!canToggleToLanguage(editorView, language)) {
    return false;
  }

  switchLanguage(editorView, language);

  return language;
}
