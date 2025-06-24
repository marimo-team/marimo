/* Copyright 2024 Marimo. All rights reserved. */
import {
  acceptCompletion,
  closeBrackets,
  closeBracketsKeymap,
  completionStatus,
  moveCompletionSelection,
  startCompletion,
} from "@codemirror/autocomplete";
import {
  history,
  historyKeymap,
  indentMore,
  indentWithTab,
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
import { lintGutter } from "@codemirror/lint";
import { EditorState, type Extension, Prec } from "@codemirror/state";
import {
  drawSelection,
  dropCursor,
  EditorView,
  highlightActiveLine,
  highlightActiveLineGutter,
  highlightSpecialChars,
  keymap,
  lineNumbers,
  rectangularSelection,
  tooltips,
} from "@codemirror/view";
import { aiExtension } from "@marimo-team/codemirror-ai";
import type { Theme } from "../../theme/useTheme";
import type { CellId } from "../cells/ids";
import type {
  CompletionConfig,
  DiagnosticsConfig,
  DisplayConfig,
  KeymapConfig,
  LSPConfig,
} from "../config/config-schema";
import { getFeatureFlag } from "../config/feature-flag";
import type { HotkeyProvider } from "../hotkeys/hotkeys";
import { store } from "../state/jotai";
import { requestEditCompletion } from "./ai/request";
import { cellBundle } from "./cells/extensions";
import type { CodemirrorCellActions } from "./cells/state";
import { jupyterHelpExtension } from "./compat/jupyter";
import { hintTooltip } from "./completion/hints";
import { completionKeymap } from "./completion/keymap";
import { cellConfigExtension } from "./config/extension";
import { copilotBundle } from "./copilot/extension";
import { historyCompartment } from "./editing/extensions";
import { scrollActiveLineIntoView } from "./extensions";
import { findReplaceBundle } from "./find-replace/extension";
import { goToDefinitionBundle } from "./go-to-definition/extension";
import { keymapBundle } from "./keymaps/keymaps";
import { getCurrentLanguageAdapter } from "./language/commands";
import { adaptiveLanguageConfiguration } from "./language/extension";
import { dndBundle } from "./misc/dnd";
import { pasteBundle } from "./misc/paste";
import { reactiveReferencesBundle } from "./reactive-references/extension";
import { dynamicReadonly } from "./readonly/extension";
import { darkTheme } from "./theme/dark";
import { lightTheme } from "./theme/light";

export interface CodeMirrorSetupOpts {
  cellId: CellId;
  showPlaceholder: boolean;
  enableAI: boolean;
  cellActions: CodemirrorCellActions;
  completionConfig: CompletionConfig;
  keymapConfig: KeymapConfig;
  theme: Theme;
  hotkeys: HotkeyProvider;
  lspConfig: LSPConfig;
  diagnosticsConfig: DiagnosticsConfig;
  displayConfig: Pick<DisplayConfig, "reference_highlighting">;
}

function getPlaceholderType(opts: CodeMirrorSetupOpts) {
  const { showPlaceholder, enableAI } = opts;
  return showPlaceholder ? "marimo-import" : enableAI ? "ai" : "none";
}

/**
 * Setup CodeMirror for a cell
 */
export const setupCodeMirror = (opts: CodeMirrorSetupOpts): Extension[] => {
  const {
    cellId,
    keymapConfig,
    hotkeys,
    enableAI,
    cellActions,
    completionConfig,
    lspConfig,
    diagnosticsConfig,
    displayConfig,
  } = opts;
  const placeholderType = getPlaceholderType(opts);

  return [
    // Editor keymaps (vim or defaults) based on user config
    keymapBundle(keymapConfig, hotkeys),
    dndBundle(),
    pasteBundle(),
    jupyterHelpExtension(),
    // Cell editing
    cellConfigExtension(
      completionConfig,
      hotkeys,
      placeholderType,
      lspConfig,
      diagnosticsConfig,
    ),
    cellBundle(cellId, hotkeys, cellActions),
    // Comes last so that it can be overridden
    basicBundle(opts),
    // Underline cmd+clickable placeholder
    goToDefinitionBundle(),
    diagnosticsConfig?.enabled ? lintGutter() : [],
    // AI edit inline
    enableAI && getFeatureFlag("inline_ai_tooltip")
      ? aiExtension({
          prompt: (req) => {
            return requestEditCompletion({
              prompt: req.prompt,
              selection: req.selection,
              codeBefore: req.codeBefore,
              codeAfter: req.codeAfter,
              language: getCurrentLanguageAdapter(req.editorView),
            });
          },
        })
      : [],
    // Readonly extension
    dynamicReadonly(store),
    // Reactive references highlighting
    reactiveReferencesBundle(
      cellId,
      displayConfig.reference_highlighting ?? false,
    ),
  ];
};

const startCompletionAtEndOfLine = (cm: EditorView): boolean => {
  const { from, to } = cm.state.selection.main;
  if (from !== to) {
    // this is a selection
    return false;
  }

  const line = cm.state.doc.lineAt(to);
  return line.text.slice(0, to - line.from).trim() === ""
    ? // in the whitespace prefix of a line
      false
    : startCompletion(cm);
};

// Based on codemirror's basicSetup extension
export const basicBundle = (opts: CodeMirrorSetupOpts): Extension[] => {
  const {
    theme,
    hotkeys,
    completionConfig,
    cellId,
    lspConfig,
    diagnosticsConfig,
  } = opts;
  const placeholderType = getPlaceholderType(opts);

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
    theme === "dark" ? darkTheme : lightTheme,

    hintTooltip(lspConfig),
    copilotBundle(completionConfig),
    foldGutter(),
    closeBrackets(),
    completionKeymap(),
    // to avoid clash with charDeleteBackward keymap
    Prec.high(keymap.of(closeBracketsKeymap)),
    bracketMatching(),
    indentOnInput(),
    indentUnit.of("    "),
    syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
    keymap.of(foldKeymap),

    ///// Language Support
    adaptiveLanguageConfiguration({
      placeholderType,
      completionConfig,
      hotkeys,
      cellId,
      lspConfig: { ...lspConfig, diagnostics: diagnosticsConfig },
    }),

    ///// Editing
    historyCompartment.of(history()),
    EditorState.allowMultipleSelections.of(true),
    findReplaceBundle(hotkeys),
    keymap.of([
      {
        key: "Tab",
        run: (cm) => {
          return (
            acceptCompletion(cm) ||
            startCompletionAtEndOfLine(cm) ||
            indentMore(cm)
          );
        },
        preventDefault: true,
      },
      {
        key: hotkeys.getHotkey("completion.moveDown").key,
        run: (cm) => {
          if (completionStatus(cm.state) !== null) {
            moveCompletionSelection(true)(cm);
            return true;
          }
          return false;
        },
        preventDefault: true,
      },
      {
        key: hotkeys.getHotkey("completion.moveUp").key,
        run: (cm) => {
          if (completionStatus(cm.state) !== null) {
            moveCompletionSelection(false)(cm);
            return true;
          }
          return false;
        },
        preventDefault: true,
      },
    ]),
    keymap.of([...historyKeymap, indentWithTab]),
  ];
};

// Use the default keymap for completion
export { completionKeymap as autocompletionKeymap } from "@codemirror/autocomplete";
