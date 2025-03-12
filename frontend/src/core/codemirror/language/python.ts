/* Copyright 2024 Marimo. All rights reserved. */
import { type Extension, Prec } from "@codemirror/state";
import type { LanguageAdapter } from "./types";
import {
  pythonLanguage,
  localCompletionSource,
  globalCompletion,
} from "@codemirror/lang-python";
import {
  foldNodeProp,
  foldInside,
  LanguageSupport,
} from "@codemirror/language";
import type { CompletionConfig, LSPConfig } from "@/core/config/config-schema";
import type { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import type { PlaceholderType } from "../config/extension";
import {
  smartPlaceholderExtension,
  clickablePlaceholderExtension,
} from "../placeholder/extensions";
import type { MovementCallbacks } from "../cells/extensions";
import {
  LanguageServerClient,
  languageServerWithTransport,
} from "@marimo-team/codemirror-languageserver";
import { resolveToWsUrl } from "@/core/websocket/createWsUrl";
import { WebSocketTransport } from "@open-rpc/client-js";
import { CellDocumentUri } from "../lsp/types";
import type { CellId } from "@/core/cells/ids";
import { NotebookLanguageServerClient } from "../lsp/notebook-lsp";
import { once } from "@/utils/once";
import { getFeatureFlag } from "@/core/config/feature-flag";
import { autocompletion } from "@codemirror/autocomplete";
import { completer } from "../completion/completer";
import { getFilenameFromDOM } from "@/core/dom/htmlUtils";
import { Paths } from "@/utils/paths";

const pylspTransport = once(() => {
  const transport = new WebSocketTransport(resolveToWsUrl("/lsp/pylsp"));
  return transport;
});

const lspClient = once<any>((lspConfig: LSPConfig) => {
  const lspClientOpts = {
    transport: pylspTransport(),
    rootUri: `file://${Paths.dirname(getFilenameFromDOM() ?? "/")}`,
    languageId: "python",
    workspaceFolders: [],
  };
  const config = lspConfig?.pylsp;

  const ignoredStyleRules = [
    // Notebooks are not really public modules and are better documented
    // by having a markdown cell with explanations instead
    "D100", // Missing docstring in public module
  ];
  const ignoredFlakeRules = [
    // The final cell in the notebook is not required to have a new line
    "W292", // No newline at end of file
    // Modules can be imported in any cell
    "E402", // Module level import not at top of file
  ];
  const settings = {
    pylsp: {
      plugins: {
        marimo_plugin: {
          enabled: true,
        },
        jedi: {
          auto_import_modules: ["marimo", "numpy"],
        },
        flake8: {
          enabled: config?.enable_flake8,
          extendIgnore: ignoredFlakeRules,
        },
        pydocstyle: {
          enabled: config?.enable_pydocstyle,
          addIgnore: ignoredStyleRules,
        },
        pylint: {
          enabled: config?.enable_pylint,
        },
        pyflakes: {
          enabled: config?.enable_pyflakes,
        },
        pylsp_mypy: {
          enabled: config?.enable_mypy,
          live_mode: true,
        },
        ruff: {
          enabled: config?.enable_ruff,
          extendIgnore: [...ignoredFlakeRules, ...ignoredStyleRules],
        },
      },
    },
  };

  // We wrap the client in a NotebookLanguageServerClient to add some
  // additional functionality to handle multiple cells
  return new NotebookLanguageServerClient(
    new LanguageServerClient({
      ...lspClientOpts,
      documentUri: "file:///unused.py", // Incorrect types
      autoClose: false,
    }),
    settings,
  ) as unknown as LanguageServerClient;
});

/**
 * Language adapter for Python.
 */
export class PythonLanguageAdapter implements LanguageAdapter {
  readonly type = "python";
  readonly defaultCode = "";

  transformIn(code: string): [string, number] {
    return [code, 0];
  }

  transformOut(code: string): [string, number] {
    return [code, 0];
  }

  isSupported(_code: string): boolean {
    return true;
  }

  getExtension(
    cellId: CellId,
    completionConfig: CompletionConfig,
    _hotkeys: HotkeyProvider,
    placeholderType: PlaceholderType,
    cellMovementCallbacks: MovementCallbacks,
    lspConfig: LSPConfig,
  ): Extension[] {
    return [
      getFeatureFlag("lsp")
        ? languageServerWithTransport({
            client: lspClient(lspConfig),
            documentUri: CellDocumentUri.of(cellId),
            transport: pylspTransport(),
            rootUri: "file:///",
            languageId: "python",
            workspaceFolders: [],
            allowHTMLContent: true,
          })
        : // Whether or not to require keypress to activate autocompletion (default
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
      customPythonLanguageSupport(),
      placeholderType === "marimo-import"
        ? Prec.highest(smartPlaceholderExtension("import marimo as mo"))
        : placeholderType === "ai"
          ? clickablePlaceholderExtension({
              beforeText: "Start coding or ",
              linkText: "generate",
              afterText: " with AI.",
              onClick: cellMovementCallbacks.aiCellCompletion,
            })
          : [],
    ];
  }
}

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

/**
 * This provide LanguageSupport for Python, but with a custom LRLanguage
 * that supports folding additional syntax nodes at the top-level.
 */
export function customPythonLanguageSupport(): LanguageSupport {
  return new LanguageSupport(customizedPython, [
    customizedPython.data.of({ autocomplete: localCompletionSource }),
    customizedPython.data.of({ autocomplete: globalCompletion }),
  ]);
}
