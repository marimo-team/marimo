/* Copyright 2024 Marimo. All rights reserved. */
import { closeBrackets, closeBracketsKeymap } from "@codemirror/autocomplete";
import { history, historyKeymap } from "@codemirror/commands";
import {
  bracketMatching,
  defaultHighlightStyle,
  foldGutter,
  foldKeymap,
  indentOnInput,
  syntaxHighlighting,
} from "@codemirror/language";
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

import { EditorState, type Extension, Prec } from "@codemirror/state";
import { oneDark } from "@codemirror/theme-one-dark";

import type { CompletionConfig, KeymapConfig } from "../config/config-schema";
import type { Theme } from "../../theme/useTheme";

import { findReplaceBundle } from "./find-replace/extension";
import {
  type CodeCallbacks,
  type MovementCallbacks,
  cellCodeEditingBundle,
  cellMovementBundle,
} from "./cells/extensions";
import type { CellId } from "../cells/ids";
import { keymapBundle } from "./keymaps/keymaps";
import { scrollActiveLineIntoView } from "./extensions";
import { copilotBundle } from "./copilot/extension";
import { hintTooltip } from "./completion/hints";
import { adaptiveLanguageConfiguration } from "./language/extension";
import { historyCompartment } from "./editing/extensions";
import { goToDefinitionBundle } from "./go-to-definition/extension";
import type { HotkeyProvider } from "../hotkeys/hotkeys";
import { lightTheme } from "./theme/light";
import { tabHandling } from "./tabs";

export interface CodeMirrorSetupOpts {
  cellId: CellId;
  showPlaceholder: boolean;
  enableAI: boolean;
  cellMovementCallbacks: MovementCallbacks;
  cellCodeCallbacks: CodeCallbacks;
  completionConfig: CompletionConfig;
  keymapConfig: KeymapConfig;
  theme: Theme;
  hotkeys: HotkeyProvider;
}

/**
 * Setup CodeMirror for a cell
 */
export const setupCodeMirror = (opts: CodeMirrorSetupOpts): Extension[] => {
  const {
    cellId,
    cellMovementCallbacks,
    cellCodeCallbacks,
    keymapConfig,
    hotkeys,
  } = opts;

  return [
    // Editor keymaps (vim or defaults) based on user config
    keymapBundle(keymapConfig, cellMovementCallbacks),
    // Cell editing
    cellMovementBundle(cellId, cellMovementCallbacks, hotkeys),
    cellCodeEditingBundle(cellId, cellCodeCallbacks, hotkeys),
    // Comes last so that it can be overridden
    basicBundle(opts),
    // Underline cmd+clickable placeholder
    goToDefinitionBundle(),
  ];
};

// Based on codemirror's basicSetup extension
export const basicBundle = (opts: CodeMirrorSetupOpts): Extension[] => {
  const { theme, hotkeys, completionConfig } = opts;

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
    theme === "dark" ? oneDark : lightTheme,

    hintTooltip(),
    copilotBundle(completionConfig),
    foldGutter(),
    closeBrackets(),
    // to avoid clash with charDeleteBackward keymap
    Prec.high(keymap.of(closeBracketsKeymap)),
    bracketMatching(),
    indentOnInput(),
    syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
    keymap.of(foldKeymap),

    ///// Language Support
    adaptiveLanguageConfiguration(opts),

    ///// Editing
    historyCompartment.of(history()),
    EditorState.allowMultipleSelections.of(true),
    findReplaceBundle(hotkeys),
    tabHandling(),
    keymap.of(historyKeymap),
  ];
};

// Use the default keymap for completion
export { completionKeymap as autocompletionKeymap } from "@codemirror/autocomplete";
