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
import {
  LanguageServerClient,
  languageServerWithTransport,
} from "codemirror-languageserver";
import { resolveToWsUrl } from "@/core/websocket/createWsUrl";
import { WebSocketTransport } from "@open-rpc/client-js";
import { CellDocumentUri } from "../lsp/types";
import type { CellId } from "@/core/cells/ids";
import { NotebookLanguageServerClient } from "../lsp/notebook-lsp";
import { once } from "@/utils/once";

const pylspTransport = () =>
  new WebSocketTransport(resolveToWsUrl("/lsp/pylsp"));

const lspClient = once(() => {
  const lspClientOpts = {
    transport: pylspTransport(),
    rootUri: "file:///",
    languageId: "python",
    workspaceFolders: null,
  };

  // We wrap the client in a NotebookLanguageServerClient to add some
  // additional functionality to handle multiple cells
  return new NotebookLanguageServerClient(
    new LanguageServerClient({
      ...lspClientOpts,
      documentUri: "file:///unused.py", // Incorrect types
      autoClose: true,
    }),
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
  ): Extension[] {
    return [
      languageServerWithTransport({
        client: lspClient(),
        documentUri: CellDocumentUri.of(cellId),
        transport: pylspTransport(),
        rootUri: "file:///",
        languageId: "python",
        workspaceFolders: null,
        allowHTMLContent: true,
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
