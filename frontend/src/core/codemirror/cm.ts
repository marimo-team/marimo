/* Copyright 2026 Marimo. All rights reserved. */
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
import { aiExtension, triggerOptions } from "@marimo-team/codemirror-ai";
import type { Theme } from "../../theme/useTheme";
import type { CellId } from "../cells/ids";
import type {
  CompletionConfig,
  DiagnosticsConfig,
  DisplayConfig,
  KeymapConfig,
  LSPConfig,
} from "../config/config-schema";
import type { HotkeyProvider } from "../hotkeys/hotkeys";
import { requestEditCompletion } from "./ai/request";
import { cellBundle } from "./cells/extensions";
import type { CodemirrorCellActions } from "./cells/state";
import { codeLensBundle } from "./code-lens/extension";
import { jupyterHelpExtension } from "./compat/jupyter";
import { hintTooltip } from "./completion/hints";
import { completionKeymap } from "./completion/keymap";
import { cellConfigExtension } from "./config/extension";
import { copilotBundle } from "./copilot/extension";
import { historyCompartment } from "./editing/extensions";
import { scrollActiveLineIntoViewExtension } from "./extensions";
import { findReplaceBundle } from "./find-replace/extension";
import { goToDefinitionBundle } from "./go-to-definition/extension";
import { keymapBundle } from "./keymaps/keymaps";
import { getCurrentLanguageAdapter } from "./language/commands";
import { adaptiveLanguageConfiguration } from "./language/extension";
import { dndBundle } from "./misc/dnd";
import { pasteBundle } from "./misc/paste";
import { stringsAutoCloseBraces } from "./misc/string-braces";
import { reactiveReferencesBundle } from "./reactive-references/extension";
import { darkTheme } from "./theme/dark";
import { lightTheme } from "./theme/light";

export interface CodeMirrorSetupOpts {
  cellId: CellId;
  showPlaceholder: boolean;
  enableAI: boolean;
  acceptCompletionOnEnter?: boolean;
  cellActions: CodemirrorCellActions;
  completionConfig: CompletionConfig;
  keymapConfig: KeymapConfig;
  theme: Theme;
  hotkeys: HotkeyProvider;
  lspConfig: LSPConfig;
  diagnosticsConfig: DiagnosticsConfig;
  displayConfig: Pick<DisplayConfig, "reference_highlighting">;
  inlineAiTooltip: boolean;
  /**
   * CSS selector for the element that CodeMirror tooltips (completions, hover,
   * signature help) should be appended to. Defaults to `#App`.
   */
  tooltipParentSelector?: string;
}

function getPlaceholderType(opts: CodeMirrorSetupOpts) {
  const { showPlaceholder, enableAI } = opts;
  return showPlaceholder ? "marimo-import" : enableAI ? "ai" : "none";
}

const CODEMIRROR_TOOLTIP_PORTAL_CLASS = "cm-tooltip-portal";

/**
 * Resolve the element that editor tooltips (completions, hover, signature help)
 * should be appended to.
 *
 * The default `#App` parent is returned directly. Custom parents are useful
 * when editors live inside a fullscreen subtree, dialog, or scoped typography
 * region. In those cases we append tooltips to a dedicated `not-prose` portal
 * inside the requested parent, reusing it across cells so surrounding typography
 * styles don't leak into editor popups.
 */
function resolveCodeMirrorTooltipParent(
  selector: string | undefined,
): HTMLElement | undefined {
  if (selector == null) {
    return document.querySelector<HTMLElement>("#App") ?? undefined;
  }

  const host = document.querySelector<HTMLElement>(selector);
  if (host == null) {
    return undefined;
  }

  const existing = host.querySelector<HTMLElement>(
    `:scope > .${CODEMIRROR_TOOLTIP_PORTAL_CLASS}`,
  );
  if (existing != null) {
    return existing;
  }

  const portal = document.createElement("div");
  // `not-prose` escapes scoped typography; `contents` keeps the wrapper
  // layout-neutral. Tooltips are `position: fixed`, so the wrapper having no
  // box doesn't affect positioning.
  portal.className = `${CODEMIRROR_TOOLTIP_PORTAL_CLASS} not-prose contents`;
  host.append(portal);
  return portal;
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
    inlineAiTooltip,
  } = opts;
  const placeholderType = getPlaceholderType(opts);

  return [
    // Editor keymaps (vim or defaults) based on user config
    keymapBundle(keymapConfig, hotkeys),
    dndBundle(),
    pasteBundle(),
    jupyterHelpExtension(),
    // Cell editing
    cellConfigExtension({
      cellId,
      completionConfig,
      hotkeys,
      placeholderType,
      lspConfig,
      diagnosticsConfig,
    }),
    cellBundle({ cellId, hotkeys, cellActions, keymapConfig }),
    // Comes last so that it can be overridden
    basicBundle(opts),
    // Underline cmd+clickable placeholder
    goToDefinitionBundle(),
    diagnosticsConfig?.enabled ? lintGutter() : [],
    // AI edit inline
    enableAI && inlineAiTooltip
      ? [
          aiExtension({
            prompt: (req) => {
              return requestEditCompletion({
                prompt: req.prompt,
                selection: req.selection,
                codeBefore: req.codeBefore,
                codeAfter: req.codeAfter,
                language: getCurrentLanguageAdapter(req.editorView),
              });
            },
          }),
          triggerOptions.of({
            hideOnBlur: true,
          }),
        ]
      : [],
    // Reactive references highlighting
    reactiveReferencesBundle(
      cellId,
      displayConfig.reference_highlighting ?? true,
    ),
    // Inline icons linking datasources/buckets/caches to their panels
    codeLensBundle(cellId),
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
    acceptCompletionOnEnter,
    cellId,
    lspConfig,
    diagnosticsConfig,
    tooltipParentSelector,
  } = opts;
  const placeholderType = getPlaceholderType(opts);
  const autoClosePairs = completionConfig.auto_close_pairs !== false;

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
      parent: resolveCodeMirrorTooltipParent(tooltipParentSelector),
    }),
    scrollActiveLineIntoViewExtension(),
    theme === "dark" ? darkTheme : lightTheme,

    hintTooltip(lspConfig),
    copilotBundle(completionConfig),
    foldGutter(),
    stringsAutoCloseBraces(),
    autoClosePairs ? closeBrackets() : [],
    completionKeymap(acceptCompletionOnEnter),
    // to avoid clash with charDeleteBackward keymap
    autoClosePairs ? Prec.high(keymap.of(closeBracketsKeymap)) : [],
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
