/* Copyright 2024 Marimo. All rights reserved. */
import {
  Compartment,
  EditorSelection,
  StateEffect,
  StateField,
} from "@codemirror/state";
import { LanguageAdapter } from "./types";
import { PythonLanguageAdapter } from "./python";
import { EditorView, Panel, keymap, showPanel } from "@codemirror/view";
import { MarkdownLanguageAdapter } from "./markdown";
import { clamp } from "@/utils/math";
import { CompletionConfig } from "@/core/config/config-schema";
import { completionConfigState } from "../config/extension";
import { historyCompartment } from "../editing/extensions";
import { history } from "@codemirror/commands";
import { formattingChangeEffect } from "../format";

export const LanguageAdapters: Record<
  LanguageAdapter["type"],
  () => LanguageAdapter
> = {
  python: () => new PythonLanguageAdapter(),
  markdown: () => new MarkdownLanguageAdapter(),
};

const LANGUAGES: LanguageAdapter[] = [
  LanguageAdapters.python(),
  LanguageAdapters.markdown(),
];

const languageCompartment = new Compartment();

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
  provide: (field) =>
    showPanel.from(field, (value) =>
      value.type === "python" ? null : createLanguagePanel,
    ),
});

// Keymap to toggle between languages
function languageToggle(completionConfig: CompletionConfig) {
  // Cycle through the language to find the next one that supports the code
  const findNextLanguage = (code: string, index: number): LanguageAdapter => {
    const language = LANGUAGES[index % LANGUAGES.length];
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
          const currentLanguageIndex = LANGUAGES.findIndex(
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
        nextLanguage.getExtension(completionConfig),
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
  const dom = document.createElement("div");
  dom.textContent = view.state.field(languageAdapterState).type;
  dom.style.padding = "0.2rem 0.5rem";
  dom.style.display = "flex";
  dom.style.justifyContent = "flex-end";
  return {
    dom,
    update(update) {
      dom.textContent = update.state.field(languageAdapterState).type;
    },
  };
}

/**
 * Set of extensions to enable adaptive language configuration.
 */
export function adaptiveLanguageConfiguration(
  completionConfig: CompletionConfig,
) {
  return [
    completionConfigState.of(completionConfig),
    languageToggle(completionConfig),
    languageCompartment.of(
      LanguageAdapters.python().getExtension(completionConfig),
    ),
    languageAdapterState,
  ];
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

export function reconfigureLanguageEffect(
  view: EditorView,
  completionConfig: CompletionConfig,
) {
  const language = view.state.field(languageAdapterState);
  return languageCompartment.reconfigure(
    language.getExtension(completionConfig),
  );
}
