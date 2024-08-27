/* Copyright 2024 Marimo. All rights reserved. */
import {
  Compartment,
  EditorSelection,
  StateEffect,
  StateField,
} from "@codemirror/state";
import type { LanguageAdapter } from "./types";
import {
  type EditorView,
  type Panel,
  keymap,
  showPanel,
} from "@codemirror/view";
import { clamp } from "@/utils/math";
import type { CompletionConfig } from "@/core/config/config-schema";
import {
  completionConfigState,
  hotkeysProviderState,
  movementCallbacksState,
  placeholderState,
} from "../config/extension";
import { historyCompartment } from "../editing/extensions";
import { history } from "@codemirror/commands";
import { formattingChangeEffect } from "../format";
import { getEditorCodeAsPython } from "./utils";
import type { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import type { CodeMirrorSetupOpts } from "../cm";
import { getLanguageAdapters, LanguageAdapters } from "./LanguageAdapters";
import { createPanel } from "../react-dom/createPanel";
import { LanguagePanelComponent } from "./panel";

/**
 * Compartment to keep track of the current language and extension.
 * When the language changes, the extensions inside the compartment will be updated.
 */
const languageCompartment = new Compartment();

/**
 * State effect to set the language adapter.
 */
const setLanguageAdapter = StateEffect.define<LanguageAdapter>();

/**
 * State field to keep track of the current language adapter.
 */
export const languageAdapterState = StateField.define<LanguageAdapter>({
  create() {
    return LanguageAdapters.python();
  },
  update(value, tr) {
    for (const effect of tr.effects) {
      if (effect.is(setLanguageAdapter)) {
        return effect.value;
      }
    }
    return value;
  },
  // Only show the panel if the language is not python
  provide: (field) =>
    showPanel.from(field, (value) => {
      if (value.type === "python") {
        return null;
      }
      return createLanguagePanel;
    }),
});

// Keymap to toggle between languages
function languageToggle() {
  const languages = getLanguageAdapters();
  // Cycle through the language to find the next one that supports the code
  const findNextLanguage = (code: string, index: number): LanguageAdapter => {
    const language = languages[index % languages.length];
    if (language.isSupported(code)) {
      return language;
    }
    return findNextLanguage(code, index + 1);
  };

  return [
    keymap.of([
      {
        key: "F4",
        preventDefault: true,
        run: (cm) => {
          // Find the next language
          const currentLanguage = cm.state.field(languageAdapterState);
          const currentLanguageIndex = languages.findIndex(
            (l) => l.type === currentLanguage.type,
          );
          const code = cm.state.doc.toString();
          const nextLanguage = findNextLanguage(code, currentLanguageIndex + 1);

          if (currentLanguage === nextLanguage) {
            return false;
          }

          updateLanguageAdapterAndCode(cm, nextLanguage);
          return true;
        },
      },
    ]),
  ];
}

function updateLanguageAdapterAndCode(
  view: EditorView,
  nextLanguage: LanguageAdapter,
) {
  const currentLanguage = view.state.field(languageAdapterState);
  const code = view.state.doc.toString();
  const completionConfig = view.state.facet(completionConfigState);
  const hotkeysProvider = view.state.facet(hotkeysProviderState);
  const placeholderType = view.state.facet(placeholderState);
  const movementCallbacks = view.state.facet(movementCallbacksState);
  // Update the code
  const [codeOut, cursorDiff1] = currentLanguage.transformOut(code);
  const [newCode, cursorDiff2] = nextLanguage.transformIn(codeOut);

  // Update the cursor position
  let cursor = view.state.selection.main.head;
  cursor += cursorDiff1;
  cursor -= cursorDiff2;
  cursor = clamp(cursor, 0, newCode.length);

  // Update the state
  view.dispatch({
    effects: [
      setLanguageAdapter.of(nextLanguage),
      languageCompartment.reconfigure(
        nextLanguage.getExtension(
          completionConfig,
          hotkeysProvider,
          placeholderType,
          movementCallbacks,
        ),
      ),
      // Clear history
      historyCompartment.reconfigure([]),
      // Let downstream extensions know that this is a formatting change
      formattingChangeEffect.of(true),
    ],
    changes: {
      from: 0,
      to: view.state.doc.length,
      insert: newCode,
    },
    selection: EditorSelection.cursor(cursor),
  });

  // Add history back
  view.dispatch({
    effects: [historyCompartment.reconfigure([history()])],
  });
}

function createLanguagePanel(view: EditorView): Panel {
  return createPanel(view, LanguagePanelComponent);
}

/**
 * Set of extensions to enable adaptive language configuration.
 */
export function adaptiveLanguageConfiguration(
  opts: Pick<
    CodeMirrorSetupOpts,
    | "completionConfig"
    | "hotkeys"
    | "showPlaceholder"
    | "enableAI"
    | "cellMovementCallbacks"
  >,
) {
  const {
    showPlaceholder,
    enableAI,
    completionConfig,
    hotkeys,
    cellMovementCallbacks,
  } = opts;

  const placeholderType = showPlaceholder
    ? "marimo-import"
    : enableAI
      ? "ai"
      : "none";

  return [
    // Store state
    completionConfigState.of(completionConfig),
    hotkeysProviderState.of(hotkeys),
    placeholderState.of(placeholderType),
    movementCallbacksState.of(cellMovementCallbacks),
    // Language adapter
    languageToggle(),
    languageCompartment.of(
      LanguageAdapters.python().getExtension(
        completionConfig,
        hotkeys,
        placeholderType,
        cellMovementCallbacks,
      ),
    ),
    languageAdapterState,
  ];
}

/**
 * Get the best language given the editors current code.
 */
export function getInitialLanguageAdapter(state: EditorView["state"]) {
  const doc = getEditorCodeAsPython({ state }).trim();
  // Empty doc defaults to Python
  if (!doc) {
    return LanguageAdapters.python();
  }

  if (LanguageAdapters.markdown().isSupported(doc)) {
    return LanguageAdapters.markdown();
  }
  if (LanguageAdapters.sql().isSupported(doc)) {
    return LanguageAdapters.sql();
  }

  return LanguageAdapters.python();
}

/**
 * Switch the language of the editor.
 */
export function switchLanguage(
  view: EditorView,
  language: LanguageAdapter["type"],
) {
  const newLanguage = LanguageAdapters[language];
  updateLanguageAdapterAndCode(view, newLanguage());
}

/**
 * Reconfigure the editor view with
 * the new language extensions.
 *
 * This is used when the language changes
 * (e.g. switching from markdown to python).
 */
export function reconfigureLanguageEffect(
  view: EditorView,
  completionConfig: CompletionConfig,
  hotkeysProvider: HotkeyProvider,
) {
  const language = view.state.field(languageAdapterState);
  const placeholderType = view.state.facet(placeholderState);
  const movementCallbacks = view.state.facet(movementCallbacksState);
  return languageCompartment.reconfigure(
    language.getExtension(
      completionConfig,
      hotkeysProvider,
      placeholderType,
      movementCallbacks,
    ),
  );
}
