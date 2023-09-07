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

import { EditorState, Extension, Prec } from "@codemirror/state";
import { oneDark } from "@codemirror/theme-one-dark";

import { CompletionConfig, KeymapConfig } from "../config";
import { Theme } from "../../theme/useTheme";

import { completer } from "@/core/codemirror/completion/completer";
import { findReplaceBundle } from "./find-replace/extension";
import {
  CodeCallbacks,
  MovementCallbacks,
  cellCodeEditingBundle,
  cellMovementBundle,
} from "./cells/extensions";
import { CellId } from "../model/ids";
import { keymapBundle } from "./keymaps/keymaps";
import {
  scrollActiveLineIntoView,
  smartPlaceholderExtension,
} from "./extensions";

export interface CodeMirrorSetupOpts {
  cellId: CellId;
  showPlaceholder: boolean;
  cellMovementCallbacks: MovementCallbacks;
  cellCodeCallbacks: CodeCallbacks;
  completionConfig: CompletionConfig;
  keymapConfig: KeymapConfig;
  theme: Theme;
}

/**
 * Setup CodeMirror for a cell
 */
export const setupCodeMirror = ({
  cellId,
  showPlaceholder,
  cellMovementCallbacks,
  cellCodeCallbacks,
  completionConfig,
  keymapConfig,
  theme,
}: CodeMirrorSetupOpts): Extension[] => {
  return [
    // Editor keymaps (vim or defaults) based on user config
    keymapBundle(keymapConfig, cellMovementCallbacks),
    // Cell editing
    cellMovementBundle(cellId, cellMovementCallbacks),
    cellCodeEditingBundle(cellId, cellCodeCallbacks),
    // Comes last so that it can be overridden
    basicBundle(completionConfig, theme),
    showPlaceholder
      ? Prec.highest(smartPlaceholderExtension("import marimo as mo"))
      : [],
  ];
};

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
export const basicBundle = (
  completionConfig: CompletionConfig,
  theme: Theme
): Extension[] => {
  return [
    ///// View
    EditorView.lineWrapping,
    drawSelection(),
    dropCursor(),
    highlightActiveLine(),
    highlightActiveLineGutter(),
    highlightSpecialChars(),
    lineNumbers(),
    rectangularSelection(),
    tooltips({ position: "absolute" }),
    scrollActiveLineIntoView(),
    theme === "dark" ? oneDark : [],

    ///// Language Support
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
    foldGutter(),
    closeBrackets(),
    keymap.of(closeBracketsKeymap),
    bracketMatching(),
    indentOnInput(),
    indentUnit.of("    "),
    syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
    keymap.of([...foldKeymap, ...lintKeymap]),

    ///// Python Support
    new LanguageSupport(customizedPython, [
      customizedPython.data.of({ autocomplete: localCompletionSource }),
      customizedPython.data.of({ autocomplete: globalCompletion }),
    ]),

    ///// Editing
    history(),
    EditorState.allowMultipleSelections.of(true),
    findReplaceBundle(),
    keymap.of([
      {
        key: "Tab",
        run: (cm) => {
          return acceptCompletion(cm) || indentMore(cm);
        },
        preventDefault: true,
      },
    ]),
    keymap.of([...historyKeymap, indentWithTab]),
  ];
};

// Use the default keymap for completion
export { completionKeymap as autocompletionKeymap } from "@codemirror/autocomplete";
