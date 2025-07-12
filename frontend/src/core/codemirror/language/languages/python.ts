/* Copyright 2024 Marimo. All rights reserved. */

import { autocompletion } from "@codemirror/autocomplete";
import {
  globalCompletion,
  localCompletionSource,
  pythonLanguage,
} from "@codemirror/lang-python";
import {
  foldInside,
  foldNodeProp,
  LanguageSupport,
} from "@codemirror/language";
import { type Extension, Prec } from "@codemirror/state";
import {
  documentUri,
  LanguageServerClient,
  languageServerWithClient,
} from "@marimo-team/codemirror-languageserver";
import type { CellId } from "@/core/cells/ids";
import { hasCapability } from "@/core/config/capabilities";
import type {
  CompletionConfig,
  DiagnosticsConfig,
  LSPConfig,
} from "@/core/config/config-schema";
import type { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import { openFile } from "@/core/network/requests";
import { Logger } from "@/utils/Logger";
import { once } from "@/utils/once";
import { cellActionsState } from "../../cells/state";
import { pythonCompletionSource } from "../../completion/completer";
import type { PlaceholderType } from "../../config/types";
import { FederatedLanguageServerClient } from "../../lsp/federated-lsp";
import { NotebookLanguageServerClient } from "../../lsp/notebook-lsp";
import { createTransport } from "../../lsp/transports";
import { CellDocumentUri, type ILanguageServerClient } from "../../lsp/types";
import { getLSPDocumentRootUri } from "../../lsp/utils";
import {
  clickablePlaceholderExtension,
  smartPlaceholderExtension,
} from "../../placeholder/extensions";
import type { LanguageAdapter } from "../types";

const pylspClient = once((lspConfig: LSPConfig) => {
  const lspClientOpts = {
    transport: createTransport("pylsp"),
    rootUri: getLSPDocumentRootUri(),
    workspaceFolders: [],
  };
  const config = lspConfig?.pylsp;

  const ignoredStyleRules = [
    // Notebooks are not really public modules and are better documented
    // by having a markdown cell with explanations instead
    "D100", // Missing docstring in public module
    "D103", // Missing docstring in public function
  ];
  const ignoredFlakeRules = [
    // The final cell in the notebook is not required to have a new line
    "W292", // No newline at end of file
    // Modules can be imported in any cell
    "E402", // Module level import not at top of file
  ];
  const ignoredRuffRules = [
    // Even ruff documentation of this rule explains it is not useful in notebooks
    "B018", // Useless expression
    // isort
    "I001", // Import block is un-sorted or un-formatted
  ];
  const settings = {
    pylsp: {
      plugins: {
        marimo_plugin: {
          enabled: true,
        },
        jedi: {
          // Modules which should be imported and use compile-time, rather
          // than static analysis; this is a trade-off between being able
          // to access more information set on runtime (e.g. via setattr)
          // vs being able to read the information from the source code
          // (e.g. comments with documentation for attributes).
          auto_import_modules: ["numpy"],
        },
        jedi_completion: {
          // Ensure that parameters are included for completion snippets.
          include_params: true,
          // Include snippets and signatures it at most 50 suggestions.
          resolve_at_most: 50,
        },
        flake8: {
          enabled: config?.enable_flake8,
          extendIgnore: ignoredFlakeRules,
        },
        pydocstyle: {
          enabled: config?.enable_pydocstyle,
          // not `addIgnore`, see https://github.com/python-lsp/python-lsp-server/issues/626
          ignore: ignoredStyleRules,
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
          extendIgnore: [
            ...ignoredFlakeRules,
            ...ignoredStyleRules,
            ...ignoredRuffRules,
          ],
        },
        signature: {
          formatter: config?.enable_ruff ? "ruff" : "black",
          line_length: 88,
        },
      },
    },
  };

  // We wrap the client in a NotebookLanguageServerClient to add some
  // additional functionality to handle multiple cells
  return new NotebookLanguageServerClient(
    new LanguageServerClient({
      ...lspClientOpts,
      autoClose: false,
    }),
    settings,
  );
});

const tyLspClient = once((_: LSPConfig) => {
  const lspClientOpts = {
    transport: createTransport("ty"),
    rootUri: getLSPDocumentRootUri(),
    workspaceFolders: [],
  };

  // We wrap the client in a NotebookLanguageServerClient to add some
  // additional functionality to handle multiple cells
  return new NotebookLanguageServerClient(
    new LanguageServerClient({
      ...lspClientOpts,
      autoClose: false,
      getWorkspaceConfiguration: (_) => [{ disableLanguageServices: true }],
    }),
    {},
  );
});

/**
 * Language adapter for Python.
 */
export class PythonLanguageAdapter implements LanguageAdapter<{}> {
  readonly type = "python";
  readonly defaultCode = "";
  readonly defaultMetadata = {};

  transformIn(code: string): [string, number, {}] {
    return [code, 0, {}];
  }

  transformOut(code: string, _metadata: {}): [string, number] {
    return [code, 0];
  }

  isSupported(_code: string): boolean {
    return true;
  }

  getExtension(
    cellId: CellId,
    completionConfig: CompletionConfig,
    hotkeys: HotkeyProvider,
    placeholderType: PlaceholderType,
    lspConfig: LSPConfig & { diagnostics: DiagnosticsConfig },
  ): Extension[] {
    const getCompletionsExtension = () => {
      const autocompleteOptions = {
        // We remove the default keymap because we use our own which
        // handles the Escape key correctly in Vim
        defaultKeymap: false,
        // Whether or not to require keypress to activate autocompletion (default
        // keymap is Ctrl+Space)
        activateOnTyping: completionConfig.activate_on_typing,
        // The Cell component handles the blur event. `closeOnBlur` is too
        // aggressive and doesn't let the user click into the completion info
        // element (which contains the docstring/type --- users might want to
        // copy paste from the docstring). The main issue is that the completion
        // tooltip is not part of the editable DOM tree:
        // https://discuss.codemirror.net/t/adding-click-event-listener-to-autocomplete-tooltip-info-panel-is-not-working/4741
        closeOnBlur: false,
      };

      const hoverOptions = {
        hideOnChange: true,
      };

      const clients: ILanguageServerClient[] = [];

      if (lspConfig?.pylsp?.enabled && hasCapability("pylsp")) {
        clients.push(pylspClient(lspConfig));
      }
      if (lspConfig?.ty?.enabled && hasCapability("ty")) {
        clients.push(tyLspClient(lspConfig));
      }

      if (clients.length > 0) {
        const client =
          clients.length === 1
            ? (clients[0] as NotebookLanguageServerClient)
            : new FederatedLanguageServerClient(clients);

        return [
          languageServerWithClient({
            client: client as unknown as LanguageServerClient,
            languageId: "python",
            allowHTMLContent: true,
            hoverConfig: hoverOptions,
            completionConfig: autocompleteOptions,
            // Default to false
            diagnosticsEnabled: lspConfig.diagnostics?.enabled ?? false,
            sendIncrementalChanges: false,
            signatureHelpEnabled: true,
            signatureActivateOnTyping: false,
            keyboardShortcuts: {
              signatureHelp: hotkeys.getHotkey("cell.signatureHelp").key,
              goToDefinition: hotkeys.getHotkey("cell.goToDefinition").key,
              rename: hotkeys.getHotkey("cell.renameSymbol").key,
            },
            // Match completions before the cursor is at the end of a word,
            // after a dot, after a slash, after a comma.
            completionMatchBefore: /(\w+|\w+\.|\(|\/|,)$/,
            onGoToDefinition: (result) => {
              Logger.debug("onGoToDefinition", result);
              if (client.documentUri === result.uri) {
                // Local definition
                return;
              }

              openFile({
                path: result.uri.replace("file://", ""),
              });
            },
          }),
          documentUri.of(CellDocumentUri.of(cellId)),
        ];
      }

      return autocompletion({
        ...autocompleteOptions,
        override: [pythonCompletionSource],
      });
    };

    return [
      getCompletionsExtension(),
      customPythonLanguageSupport(),
      getPlaceholderExtension(placeholderType),
    ];
  }
}

function getPlaceholderExtension(placeholderType: PlaceholderType): Extension {
  if (placeholderType === "marimo-import") {
    return Prec.highest(smartPlaceholderExtension("import marimo as mo"));
  }

  if (placeholderType === "ai") {
    return clickablePlaceholderExtension({
      beforeText: "Start coding or ",
      linkText: "generate",
      afterText: " with AI.",
      onClick: (ev) => {
        const cellActions = ev.state.facet(cellActionsState);
        cellActions.aiCellCompletion();
      },
    });
  }

  return [];
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
