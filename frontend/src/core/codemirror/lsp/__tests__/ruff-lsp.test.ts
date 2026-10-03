/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it, vi } from "vitest";
import type * as LSP from "vscode-languageserver-protocol";
import { RuffLanguageServerClient } from "../ruff-lsp";
import type { ILanguageServerClient } from "../types";

function createClient() {
  return {
    ready: true,
    capabilities: { hoverProvider: true },
    clientCapabilities: {},
    initializePromise: Promise.resolve(),
    hasCapability: vi.fn().mockReturnValue(true),
    initialize: vi.fn(),
    close: vi.fn(),
    onNotification: vi.fn().mockReturnValue(() => true),
    textDocumentDidOpen: vi.fn(),
    textDocumentDidChange: vi.fn(),
    textDocumentDidClose: vi.fn(),
    textDocumentWillSave: vi.fn(),
    textDocumentWillSaveWaitUntil: vi.fn(),
    textDocumentDidSave: vi.fn(),
    textDocumentHover: vi.fn(),
    textDocumentCompletion: vi.fn(),
    completionItemResolve: vi.fn(),
    textDocumentDefinition: vi.fn(),
    textDocumentCodeAction: vi.fn(),
    codeActionResolve: vi.fn(),
    textDocumentRename: vi.fn(),
    textDocumentPrepareRename: vi.fn(),
    textDocumentSignatureHelp: vi.fn(),
    processNotification: vi.fn(),
    notify: vi.fn(),
  } satisfies ILanguageServerClient & {
    processNotification: unknown;
    notify: unknown;
  };
}

describe("RuffLanguageServerClient", () => {
  it("filters notebook-only warnings and forwards empty publications", () => {
    const child = createClient();
    const client = new RuffLanguageServerClient(child, {});
    const listener = vi.fn();
    client.onNotification(listener);
    const diagnostic = (code: string): LSP.Diagnostic => ({
      code,
      source: "Ruff",
      message: code,
      range: {
        start: { line: 0, character: 0 },
        end: { line: 0, character: 1 },
      },
    });
    const notebookWarnings = [
      "D100",
      "D103",
      "W292",
      "E402",
      "E302",
      "E305",
      "B018",
      "I001",
    ].map(diagnostic);
    const lintWarning = diagnostic("E711");
    const publish = child.onNotification.mock.calls[0][0];
    const notification = {
      jsonrpc: "2.0" as const,
      method: "textDocument/publishDiagnostics" as const,
      params: {
        uri: "file:///cell.py",
        version: 1,
        diagnostics: [...notebookWarnings, lintWarning],
      },
    };
    publish(notification);
    expect(listener.mock.lastCall?.[0].params).toEqual({
      ...notification.params,
      diagnostics: [lintWarning],
    });
    publish({
      ...notification,
      params: { ...notification.params, diagnostics: notebookWarnings },
    });
    expect(listener.mock.lastCall?.[0].params.diagnostics).toEqual([]);
  });

  it("leaves Python hover to the other server", () => {
    const client = new RuffLanguageServerClient(createClient(), {});
    expect(client.hasCapability("textDocument/hover")).toBe(false);
    expect(client.hasCapability("textDocument/codeAction")).toBe(true);
  });
});
