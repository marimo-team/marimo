/* Copyright 2024 Marimo. All rights reserved. */

import type { EditorView } from "@codemirror/view";
import { getEditorCodeAsPython } from "./language/utils";
import { languageAdapterState, switchLanguage } from "./language/extension";
import { LanguageAdapters } from "./language/LanguageAdapters";
import type { LanguageAdapterType } from "./language/types";

/**
 * Get the current mode of the editor view.
 */
export function getEditorViewMode(
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
  if (!editorView || getEditorViewMode(editorView) === language) {
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
