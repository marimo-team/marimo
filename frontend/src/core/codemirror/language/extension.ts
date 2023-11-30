/* Copyright 2023 Marimo. All rights reserved. */
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

const LANGUAGES = [new PythonLanguageAdapter(), new MarkdownLanguageAdapter()];

const languageCompartment = new Compartment();

const updateLanguageAdapter = StateEffect.define<LanguageAdapter>();

export const languageAdapterState = StateField.define<LanguageAdapter>({
  create() {
    return LANGUAGES[0];
  },
  update(value, tr) {
    for (const effect of tr.effects) {
      if (effect.is(updateLanguageAdapter)) {
        return effect.value;
      }
    }
    return value;
  },
  provide: (field) =>
    showPanel.from(field, (value) =>
      value.type === "python" ? null : createLanguagePanel
    ),
});

// Keymap to toggle between languages
function languageToggle() {
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
          const currentLanguageIndex = LANGUAGES.indexOf(currentLanguage);
          const code = cm.state.doc.toString();
          const nextLanguage = findNextLanguage(code, currentLanguageIndex + 1);

          if (currentLanguage === nextLanguage) {
            return false;
          }

          // Update the code
          const [codeOut, cursorDiff1] = currentLanguage.transformOut(code);
          const [newCode, cursorDiff2] = nextLanguage.transformIn(codeOut);

          // Update the cursor position
          let cursor = cm.state.selection.main.head;
          cursor += cursorDiff1;
          cursor -= cursorDiff2;
          cursor = clamp(cursor, 0, newCode.length);

          // Update the state
          cm.dispatch({
            effects: [
              updateLanguageAdapter.of(nextLanguage),
              languageCompartment.reconfigure(nextLanguage.getExtension()),
            ],
            changes: {
              from: 0,
              to: cm.state.doc.length,
              insert: newCode,
            },
            selection: EditorSelection.cursor(cursor),
          });
          return true;
        },
      },
    ]),
  ];
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

export function adaptiveLanguageConfiguration() {
  return [
    languageToggle(),
    languageCompartment.of(new PythonLanguageAdapter().getExtension()),
    languageAdapterState,
  ];
}
