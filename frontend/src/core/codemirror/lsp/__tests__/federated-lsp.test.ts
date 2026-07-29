/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it, type Mocked, vi } from "vitest";
import type * as LSP from "vscode-languageserver-protocol";
import { FederatedLanguageServerClient } from "../federated-lsp";
import type { ILanguageServerClient } from "../types";

function createClient(
  supportedMethods: string[] = [],
): Mocked<ILanguageServerClient> {
  const client: Mocked<ILanguageServerClient> = {
    ready: true,
    capabilities: {},
    initializePromise: Promise.resolve(),
    clientCapabilities: {},
    initialize: vi.fn(),
    close: vi.fn(),
    hasCapability: vi.fn((method) => supportedMethods.includes(method)),
    textDocumentDidOpen: vi.fn().mockResolvedValue(false),
    textDocumentDidChange: vi.fn(),
    textDocumentDidClose: vi.fn(),
    textDocumentWillSave: vi.fn(),
    textDocumentWillSaveWaitUntil: vi.fn().mockResolvedValue(null),
    textDocumentDidSave: vi.fn(),
    textDocumentHover: vi.fn().mockResolvedValue({ contents: [] }),
    textDocumentCompletion: vi.fn().mockResolvedValue(null),
    completionItemResolve: vi.fn(),
    textDocumentDefinition: vi.fn().mockResolvedValue(null),
    textDocumentCodeAction: vi.fn().mockResolvedValue(null),
    codeActionResolve: vi.fn(),
    textDocumentRename: vi.fn().mockResolvedValue(null),
    textDocumentPrepareRename: vi.fn().mockResolvedValue(null),
    textDocumentSignatureHelp: vi.fn().mockResolvedValue(null),
    onNotification: vi.fn().mockReturnValue(() => true),
  };
  return client;
}

describe("FederatedLanguageServerClient", () => {
  it("routes requests using dynamic method capabilities", async () => {
    const staticOnlyClient = createClient();
    const dynamicClient = createClient(["textDocument/definition"]);
    const definition: LSP.Location = {
      uri: "file:///definition.py",
      range: {
        start: { line: 1, character: 2 },
        end: { line: 1, character: 5 },
      },
    };
    dynamicClient.textDocumentDefinition.mockResolvedValue(definition);
    const client = new FederatedLanguageServerClient([
      staticOnlyClient,
      dynamicClient,
    ]);
    const params: LSP.DefinitionParams = {
      textDocument: { uri: "file:///notebook.py" },
      position: { line: 0, character: 0 },
    };

    await expect(client.textDocumentDefinition(params)).resolves.toEqual(
      definition,
    );
    expect(client.hasCapability("textDocument/definition")).toBe(true);
    expect(staticOnlyClient.textDocumentDefinition).not.toHaveBeenCalled();
    expect(dynamicClient.textDocumentDefinition).toHaveBeenCalledWith(params);
  });

  it("prefers the first client's willSaveWaitUntil edits regardless of latency", async () => {
    const slowEdits: LSP.TextEdit[] = [
      {
        range: {
          start: { line: 0, character: 0 },
          end: { line: 0, character: 1 },
        },
        newText: "first",
      },
    ];
    const first = createClient();
    const second = createClient();
    // Answers last, but still wins
    first.textDocumentWillSaveWaitUntil.mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve(slowEdits), 5)),
    );
    second.textDocumentWillSaveWaitUntil.mockResolvedValue([
      {
        range: {
          start: { line: 1, character: 0 },
          end: { line: 1, character: 1 },
        },
        newText: "second",
      },
    ]);
    const client = new FederatedLanguageServerClient([first, second]);

    await expect(
      client.textDocumentWillSaveWaitUntil({
        textDocument: { uri: "file:///notebook.py" },
        reason: 1,
      }),
    ).resolves.toEqual(slowEdits);
    expect(second.textDocumentWillSaveWaitUntil).toHaveBeenCalled();
  });

  it("skips clients that reject willSaveWaitUntil", async () => {
    const failing = createClient();
    const working = createClient();
    const edits: LSP.TextEdit[] = [
      {
        range: {
          start: { line: 0, character: 0 },
          end: { line: 0, character: 1 },
        },
        newText: "ok",
      },
    ];
    failing.textDocumentWillSaveWaitUntil.mockRejectedValue(
      new Error("server exploded"),
    );
    working.textDocumentWillSaveWaitUntil.mockResolvedValue(edits);
    const client = new FederatedLanguageServerClient([failing, working]);

    await expect(
      client.textDocumentWillSaveWaitUntil({
        textDocument: { uri: "file:///notebook.py" },
        reason: 1,
      }),
    ).resolves.toEqual(edits);
  });

  it("fans out document lifecycle and save notifications", async () => {
    const first = createClient();
    const second = createClient();
    second.textDocumentDidOpen.mockResolvedValue(true);
    const client = new FederatedLanguageServerClient([first, second]);
    const openParams: LSP.DidOpenTextDocumentParams = {
      textDocument: {
        uri: "file:///notebook.py",
        languageId: "python",
        version: 1,
        text: "value = 1",
      },
    };
    const closeParams: LSP.DidCloseTextDocumentParams = {
      textDocument: { uri: "file:///notebook.py" },
    };
    const saveParams: LSP.DidSaveTextDocumentParams = {
      textDocument: { uri: "file:///notebook.py" },
      text: "value = 1",
    };

    await expect(client.textDocumentDidOpen(openParams)).resolves.toBe(true);
    await client.textDocumentDidClose(closeParams);
    await client.textDocumentDidSave(saveParams);

    for (const child of [first, second]) {
      expect(child.textDocumentDidOpen).toHaveBeenCalledWith(openParams);
      expect(child.textDocumentDidClose).toHaveBeenCalledWith(closeParams);
      expect(child.textDocumentDidSave).toHaveBeenCalledWith(saveParams);
    }
  });
});
