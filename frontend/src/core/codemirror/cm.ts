/* Copyright 2024 Marimo. All rights reserved. */
import {
  acceptCompletion,
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
  bracketMatching,
  defaultHighlightStyle,
  foldGutter,
  foldKeymap,
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

import { CompletionConfig, KeymapConfig } from "../config/config-schema";
import { Theme } from "../../theme/useTheme";

import { findReplaceBundle } from "./find-replace/extension";
import {
  CodeCallbacks,
  MovementCallbacks,
  cellCodeEditingBundle,
  cellMovementBundle,
} from "./cells/extensions";
import { CellId } from "../cells/ids";
import { keymapBundle } from "./keymaps/keymaps";
import {
  scrollActiveLineIntoView,
  smartPlaceholderExtension,
} from "./extensions";
import { copilotBundle } from "./copilot/extension";
import { hintTooltip } from "./completion/hints";
import { adaptiveLanguageConfiguration } from "./language/extension";
import { historyCompartment } from "./editing/extensions";

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

// Based on codemirror's basicSetup extension
export const basicBundle = (
  completionConfig: CompletionConfig,
  theme: Theme,
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
    tooltips({
      // Having fixed position prevents tooltips from being repositioned
      // and bouncing distractingly
      position: "fixed",
      // This the z-index multiple tooltips being stacked
      // For example, if we have a hover tooltip and a completion tooltip
      parent: document.querySelector<HTMLElement>("#App") ?? undefined,
    }),
    scrollActiveLineIntoView(),
    theme === "dark" ? oneDark : [],

    hintTooltip(),
    copilotBundle(),
    foldGutter(),
    closeBrackets(),
    // to avoid clash with charDeleteBackward keymap
    Prec.high(keymap.of(closeBracketsKeymap)),
    bracketMatching(),
    indentOnInput(),
    indentUnit.of("    "),
    syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
    keymap.of([...foldKeymap, ...lintKeymap]),

    ///// Language Support
    adaptiveLanguageConfiguration(completionConfig),

    ///// Editing
    historyCompartment.of(history()),
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
