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
  it("waits for every server to initialize", async () => {
    const first = createClient();
    const second = createClient();
    let finishInitialization: () => void = () => {};
    second.initializePromise = new Promise<void>((resolve) => {
      finishInitialization = resolve;
    });
    const client = new FederatedLanguageServerClient([first, second]);
    const ready = vi.fn();
    const initialized = client.initializePromise.then(ready);
    await Promise.resolve();
    await Promise.resolve();
    expect(ready).not.toHaveBeenCalled();
    finishInitialization();
    await initialized;
    expect(ready).toHaveBeenCalledOnce();
  });

  it.each(["change", "close"])(
    "does not reuse stale diagnostic ranges after a document %s",
    async (event) => {
      const first = createClient();
      const second = createClient();
      const client = new FederatedLanguageServerClient([first, second]);
      const listener = vi.fn();
      client.onNotification(listener);
      const uri = "file:///cell.py";
      const diagnostic: LSP.Diagnostic = {
        message: "old text",
        range: {
          start: { line: 3, character: 0 },
          end: { line: 3, character: 1 },
        },
      };
      first.onNotification.mock.calls[0][0]({
        jsonrpc: "2.0",
        method: "textDocument/publishDiagnostics",
        params: { uri, diagnostics: [diagnostic] },
      });
      await (event === "change"
        ? client.textDocumentDidChange({
            textDocument: { uri, version: 2 },
            contentChanges: [{ text: "new text" }],
          })
        : client.textDocumentDidClose({ textDocument: { uri } }));
      second.onNotification.mock.calls[0][0]({
        jsonrpc: "2.0",
        method: "textDocument/publishDiagnostics",
        params: { uri, diagnostics: [] },
      });
      expect(listener.mock.lastCall?.[0].params.diagnostics).toEqual([]);
    },
  );

  it("forwards protocol notifications without treating them as diagnostics", () => {
    const child = createClient();
    const client = new FederatedLanguageServerClient([child]);
    const listener = vi.fn();
    client.onNotification(listener);
    // The underlying client emits a broader set than its declared type.
    const notification = {
      jsonrpc: "2.0",
      method: "window/logMessage",
      params: { type: 3, message: "ready" },
    } as unknown as Parameters<
      Parameters<ILanguageServerClient["onNotification"]>[0]
    >[0];
    child.onNotification.mock.calls[0][0](notification);
    expect(listener).toHaveBeenCalledWith(notification);
  });

  it("keeps another subscriber's diagnostics when one unsubscribes", () => {
    const first = createClient();
    const second = createClient();
    const client = new FederatedLanguageServerClient([first, second]);
    const unsubscribe = client.onNotification(vi.fn());
    const listener = vi.fn();
    client.onNotification(listener);
    const diagnostic: LSP.Diagnostic = {
      message: "remaining",
      range: {
        start: { line: 0, character: 0 },
        end: { line: 0, character: 1 },
      },
    };
    first.onNotification.mock.calls[1][0]({
      jsonrpc: "2.0",
      method: "textDocument/publishDiagnostics",
      params: { uri: "file:///cell.py", diagnostics: [diagnostic] },
    });
    unsubscribe();
    second.onNotification.mock.calls[1][0]({
      jsonrpc: "2.0",
      method: "textDocument/publishDiagnostics",
      params: { uri: "file:///cell.py", diagnostics: [] },
    });
    expect(listener.mock.lastCall?.[0].params.diagnostics).toEqual([
      diagnostic,
    ]);
  });

  it("keeps diagnostics from each server when another publishes or clears", () => {
    const ty = createClient();
    const ruff = createClient();
    const client = new FederatedLanguageServerClient([ty, ruff]);
    const listener = vi.fn();
    const unsubscribe = client.onNotification(listener);
    const uri = "file:///cell.py";
    const diagnostic = (source: string): LSP.Diagnostic => ({
      range: {
        start: { line: 0, character: 0 },
        end: { line: 0, character: 1 },
      },
      message: source,
      source,
    });
    const tyDiagnostic = diagnostic("ty");
    const ruffDiagnostic = diagnostic("Ruff");
    const publish = (
      child: Mocked<ILanguageServerClient>,
      diagnostics: LSP.Diagnostic[],
      version: number,
      documentUri = uri,
    ) => {
      child.onNotification.mock.calls[0][0]({
        jsonrpc: "2.0",
        method: "textDocument/publishDiagnostics",
        params: { uri: documentUri, version, diagnostics },
      });
    };

    publish(ty, [tyDiagnostic], 10);
    publish(ruff, [ruffDiagnostic], 1);
    expect(listener.mock.lastCall?.[0].params.diagnostics).toEqual([
      tyDiagnostic,
      ruffDiagnostic,
    ]);
    const firstVersion = listener.mock.calls[0][0].params.version;
    expect(listener.mock.lastCall?.[0].params.version).toBeGreaterThan(
      firstVersion,
    );

    publish(ruff, [], 2);
    expect(listener.mock.lastCall?.[0].params.diagnostics).toEqual([
      tyDiagnostic,
    ]);
    publish(ruff, [ruffDiagnostic], 3, "file:///other-cell.py");
    expect(listener.mock.lastCall?.[0].params.diagnostics).toEqual([
      ruffDiagnostic,
    ]);
    publish(ty, [], 11);
    expect(listener.mock.lastCall?.[0].params.diagnostics).toEqual([]);
    expect(unsubscribe()).toBe(true);
  });

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
