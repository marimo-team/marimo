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
import type { CompletionConfig } from "@/core/config/config-schema";
import type { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import type { PlaceholderType } from "../config/extension";
import {
  smartPlaceholderExtension,
  clickablePlaceholderExtension,
} from "../placeholder/extensions";
import type { MovementCallbacks } from "../cells/extensions";
import { languageServerWithTransport } from "codemirror-languageserver";
import { resolveToWsUrl } from "@/core/websocket/createWsUrl";
import { WebSocketTransport } from "@open-rpc/client-js";
import { NotebookLanguageServerClient } from "../lsp/notebook-lsp";

// @ts-expect-error Extending private class
class MarimoLanguageServerClient extends NotebookLanguageServerClient {
  public override request(method: string, params: any, timeout: number) {
    console.debug("LSP request", method, params);
    if (method === "initialize") {
      params = {
        ...params,
        // startup options
      };
    }
    // @ts-expect-error
    const promise = super.request(method, params, timeout);
    if (method === "initialize") {
      promise.then(() =>
        this.notify("workspace/didChangeConfiguration", {
          settings: {
            pylsp: {
              plugins: {
                jedi: {
                  auto_import_modules: ["marimo", "numpy"],
                },
              },
            },
          },
        }),
      );
    }
    return promise;
  }
  private override notify(method: string, params: any) {
    console.debug("LSP notification", method, params);
    // @ts-expect-error
    return super.notify(method, params);
  }
}

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
    completionConfig: CompletionConfig,
    _hotkeys: HotkeyProvider,
    placeholderType: PlaceholderType,
    cellMovementCallbacks: MovementCallbacks,
  ): Extension[] {
    const serverUri = resolveToWsUrl("/lsp/pylsp");
    const options = {
      transport: new WebSocketTransport(serverUri),
      rootUri: "file:///",
      documentUri: "file:///__marimo__.py",
      languageId: "python",
      workspaceFolders: null,
    };
    return [
      // Whether or not to require keypress to activate autocompletion (default
      // keymap is Ctrl+Space)
      // autocompletion({
      //   activateOnTyping: completionConfig.activate_on_typing,
      //   // The Cell component handles the blur event. `closeOnBlur` is too
      //   // aggressive and doesn't let the user click into the completion info
      //   // element (which contains the docstring/type --- users might want to
      //   // copy paste from the docstring). The main issue is that the completion
      //   // tooltip is not part of the editable DOM tree:
      //   // https://discuss.codemirror.net/t/adding-click-event-listener-to-autocomplete-tooltip-info-panel-is-not-working/4741
      //   closeOnBlur: false,
      //   override: [completer],
      // }),
      // TODO: use one client per marimo notebook, merge cells
      languageServerWithTransport({
        // @ts-expect-error
        client: new MarimoLanguageServerClient({
          ...options,
          autoClose: true,
        }),
        allowHTMLContent: true,
        ...options,
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
