/* Copyright 2023 Marimo. All rights reserved. */
import {
  acceptCompletion,
  autocompletion,
  closeBrackets,
  closeBracketsKeymap,
} from "@codemirror/autocomplete";
import {
  history,
  historyKeymap,
  indentWithTab,
  indentMore,
} from "@codemirror/commands";
import {
  pythonLanguage,
  localCompletionSource,
  globalCompletion,
} from "@codemirror/lang-python";
import {
  bracketMatching,
  defaultHighlightStyle,
  foldGutter,
  foldInside,
  foldKeymap,
  foldNodeProp,
  LanguageSupport,
  indentOnInput,
  indentUnit,
  syntaxHighlighting,
} from "@codemirror/language";
import { lintKeymap } from "@codemirror/lint";
import {
  drawSelection,
  dropCursor,
  highlightActiveLine,
  highlightActiveLineGutter,
  highlightSpecialChars,
  lineNumbers,
  keymap,
  rectangularSelection,
  tooltips,
  EditorView,
} from "@codemirror/view";

import { EditorState, Extension } from "@codemirror/state";
import { oneDark } from "@codemirror/theme-one-dark";

import { CompletionConfig, KeymapConfig } from "../config";
import { Theme } from "../../theme/useTheme";

import { completer } from "@/core/codemirror/completion/completer";
import { findReplaceBundle } from "./find-replace/extension";
import { keymapBundle } from "./keymaps/keymaps";

// Customize python to support folding some additional syntax nodes
const customizedPython = pythonLanguage.configure({
  props: [
    foldNodeProp.add({
      ParenthesizedExpression: foldInside,
      // Fold function calls whose arguments are split over multiple lines
      ArgList: foldInside,
    }),
  ],
});

// Based on codemirror's basicSetup extension
export const setup = (
  completionConfig: CompletionConfig,
  keymapConfig: KeymapConfig,
  theme: Theme
): Extension[] => {
  return [
    // make sure this comes first since it contains keymaps based on user config
    keymapBundle(keymapConfig),

    // Whether or not to require keypress to activate autocompletion (default
    // keymap is Ctrl+Space)
    autocompletion({
      activateOnTyping: completionConfig.activate_on_typing,
      // The Cell component handles the blur event. `closeOnBlur` is too
      // aggressive and doesn't let the user click into the completion info
      // element (which contains the docstring/type --- users might want to
      // copy paste from the docstring). The main issue is that the completion
      // tooltip is not part of the editable DOM tree:
      // https://discuss.codemirror.net/t/adding-click-event-listener-to-autocomplete-tooltip-info-panel-is-not-working/4741
      closeOnBlur: false,
      override: [completer],
    }),
    tooltips({ position: "absolute" }),
    EditorView.lineWrapping,
    lineNumbers(),
    highlightActiveLineGutter(),
    highlightSpecialChars(),
    history(),
    foldGutter(),
    drawSelection(),
    dropCursor(),
    theme === "dark" ? oneDark : [],
    EditorState.allowMultipleSelections.of(true),
    indentOnInput(),
    indentUnit.of("    "),
    syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
    bracketMatching(),
    closeBrackets(),
    rectangularSelection(),
    highlightActiveLine(),
    keymap.of([
      {
        key: "Tab",
        run: (cm) => {
          return acceptCompletion(cm) || indentMore(cm);
        },
        preventDefault: true,
      },
    ]),
    keymap.of([
      ...closeBracketsKeymap,
      ...historyKeymap,
      ...foldKeymap,
      ...lintKeymap,
      indentWithTab,
    ]),
    keymap.of([
      {
        key: "Escape",
        preventDefault: true,
        run: (cm) => {
          cm.contentDOM.blur();
          return true;
        },
      },
    ]),
    findReplaceBundle(),
    new LanguageSupport(customizedPython, [
      customizedPython.data.of({ autocomplete: localCompletionSource }),
      customizedPython.data.of({ autocomplete: globalCompletion }),
    ]),
  ];
};

// Use the default keymap for completion
export { completionKeymap as autocompletionKeymap } from "@codemirror/autocomplete";
