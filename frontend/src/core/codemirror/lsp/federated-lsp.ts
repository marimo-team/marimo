/* Copyright 2026 Marimo. All rights reserved. */

import type * as LSP from "vscode-languageserver-protocol";
import { Objects } from "@/utils/objects";
import type { ILanguageServerClient, RoutableLspMethod } from "./types";
import { getLspDocumentUri } from "./utils";

function removeFalseyValues<T extends object>(obj: T): T {
  return Objects.filter(obj, (value) => value !== false && value !== null) as T;
}

function mergeDictsIgnoreFalsey<T extends object>(dicts: T[]): T {
  const filteredDicts = dicts.map(removeFalseyValues);
  return Object.assign({}, ...filteredDicts);
}

export class FederatedLanguageServerClient implements ILanguageServerClient {
  private readonly clients: ILanguageServerClient[] = [];
  public readonly documentUri: string;

  constructor(clients: ILanguageServerClient[]) {
    this.clients = clients;
    this.documentUri = getLspDocumentUri();
  }

  onNotification(
    listener: (n: {
      jsonrpc: "2.0";
      id?: null | undefined;
      method: "textDocument/publishDiagnostics";
      params: LSP.PublishDiagnosticsParams;
    }) => void,
  ): () => boolean {
    const callbacks: (() => boolean)[] = [];
    for (const client of this.clients) {
      callbacks.push(client.onNotification(listener));
    }
    return () => {
      for (const cb of callbacks) {
        cb();
      }
      return true;
    };
  }

  get clientCapabilities(): LSP.ClientCapabilities | undefined {
    const capabilities = this.clients
      .map((client) => {
        if (client.clientCapabilities) {
          if (typeof client.clientCapabilities === "function") {
            return client.clientCapabilities({});
          }
          return client.clientCapabilities;
        }
        return undefined;
      })
      .filter((c): c is LSP.ClientCapabilities => c != null);

    return mergeDictsIgnoreFalsey<LSP.ClientCapabilities>(capabilities);
  }

  get ready(): boolean {
    return this.clients.some((client) => client.ready);
  }

  set ready(value: boolean) {
    this.clients.forEach((client) => {
      client.ready = value;
    });
  }

  get capabilities(): LSP.ServerCapabilities | null {
    const capabilities = this.clients
      .map((client) => client.capabilities)
      .filter((c): c is LSP.ServerCapabilities => c !== null);
    return mergeDictsIgnoreFalsey<LSP.ServerCapabilities>(capabilities);
  }

  set capabilities(value: LSP.ServerCapabilities) {
    this.clients.forEach((client) => {
      client.capabilities = value;
    });
  }

  get initializePromise(): Promise<void> {
    return this.clients[0].initializePromise;
  }

  set initializePromise(value: Promise<void>) {
    this.clients.forEach((client) => {
      client.initializePromise = value;
    });
  }

  private firstWithMethod(
    method: RoutableLspMethod,
  ): ILanguageServerClient | undefined {
    return this.clients.find((client) => client.hasCapability(method));
  }

  private clientsWithMethod(
    method: RoutableLspMethod,
  ): ILanguageServerClient[] {
    return this.clients.filter((client) => client.hasCapability(method));
  }

  hasCapability(method: string): boolean {
    return this.clients.some((client) => client.hasCapability(method));
  }

  async initialize(): Promise<void> {
    await Promise.all(this.clients.map((client) => client.initialize()));
  }

  async close(): Promise<void> {
    await Promise.all(this.clients.map((client) => client.close()));
  }

  async textDocumentDidChange(
    params: LSP.DidChangeTextDocumentParams,
  ): Promise<void> {
    await Promise.all(
      this.clients.map((client) => client.textDocumentDidChange(params)),
    );
  }

  async completionItemResolve(
    item: LSP.CompletionItem,
  ): Promise<LSP.CompletionItem> {
    const client = this.firstWithMethod("textDocument/completion");
    if (client) {
      return client.completionItemResolve(item);
    }
    return item;
  }

  async textDocumentCodeAction(
    params: LSP.CodeActionParams,
  ): Promise<(LSP.Command | LSP.CodeAction)[] | null> {
    const client = this.firstWithMethod("textDocument/codeAction");
    if (client) {
      return client.textDocumentCodeAction(params);
    }
    return null;
  }

  async codeActionResolve(action: LSP.CodeAction): Promise<LSP.CodeAction> {
    const client = this.firstWithMethod("textDocument/codeAction");
    return client ? client.codeActionResolve(action) : action;
  }

  async textDocumentRename(
    params: LSP.RenameParams,
  ): Promise<LSP.WorkspaceEdit | null> {
    const client = this.firstWithMethod("textDocument/rename");
    if (client) {
      return client.textDocumentRename(params);
    }
    return null;
  }

  async textDocumentPrepareRename(
    params: LSP.PrepareRenameParams,
  ): Promise<LSP.PrepareRenameResult | null> {
    const client = this.firstWithMethod("textDocument/prepareRename");
    if (client) {
      return client.textDocumentPrepareRename(params);
    }
    return null;
  }

  async textDocumentSignatureHelp(
    params: LSP.SignatureHelpParams,
  ): Promise<LSP.SignatureHelp | null> {
    const client = this.firstWithMethod("textDocument/signatureHelp");
    if (client) {
      return client.textDocumentSignatureHelp(params);
    }
    return null;
  }

  // Merge completions from all clients
  async textDocumentCompletion(
    params: LSP.CompletionParams,
  ): Promise<LSP.CompletionList | LSP.CompletionItem[] | null> {
    const clients = this.clientsWithMethod("textDocument/completion");
    const results = await Promise.allSettled(
      clients.map((client) => client.textDocumentCompletion(params)),
    );

    return mergeCompletions(results);
  }

  async textDocumentDefinition(
    params: LSP.DefinitionParams,
  ): Promise<LSP.Definition | LSP.LocationLink[] | null> {
    const client = this.firstWithMethod("textDocument/definition");
    if (client) {
      return client.textDocumentDefinition(params);
    }
    return null;
  }

  async textDocumentDidOpen(
    params: LSP.DidOpenTextDocumentParams,
  ): Promise<boolean> {
    const results = await Promise.all(
      this.clients.map((client) => client.textDocumentDidOpen(params)),
    );

    return results.some((result) => result !== false);
  }

  async textDocumentDidClose(
    params: LSP.DidCloseTextDocumentParams,
  ): Promise<void> {
    await Promise.all(
      this.clients.map((client) => client.textDocumentDidClose(params)),
    );
  }

  async textDocumentWillSave(
    params: LSP.WillSaveTextDocumentParams,
  ): Promise<void> {
    await Promise.all(
      this.clients.map((client) => client.textDocumentWillSave(params)),
    );
  }

  async textDocumentWillSaveWaitUntil(
    params: LSP.WillSaveTextDocumentParams,
  ): Promise<LSP.TextEdit[] | null> {
    // This blocks the save, so query concurrently rather than paying the sum of
    // the servers' latencies. The earliest client that returned edits still
    // wins, so the result doesn't depend on who answers first.
    const results = await Promise.allSettled(
      this.clients.map((client) =>
        client.textDocumentWillSaveWaitUntil(params),
      ),
    );

    for (const result of results) {
      if (result.status === "fulfilled" && result.value?.length) {
        return result.value;
      }
    }
    return null;
  }

  async textDocumentDidSave(
    params: LSP.DidSaveTextDocumentParams,
  ): Promise<void> {
    await Promise.all(
      this.clients.map((client) => client.textDocumentDidSave(params)),
    );
  }

  async textDocumentHover(params: LSP.HoverParams): Promise<LSP.Hover> {
    for (const client of this.clients) {
      if (!client.hasCapability("textDocument/hover")) {
        continue;
      }
      const result = await client.textDocumentHover(params);
      if (result) {
        return result;
      }
    }
    return { contents: [] };
  }
}

function mergeCompletions(
  results: PromiseSettledResult<
    LSP.CompletionList | LSP.CompletionItem[] | null
  >[],
): LSP.CompletionList {
  const completions: LSP.CompletionItem[] = [];
  let isIncomplete = false;

  for (const result of results) {
    if (result.status === "fulfilled") {
      const res = result.value;
      if (res == null) {
        continue;
      }

      if (Array.isArray(res)) {
        completions.push(...res);
      }

      if ("items" in res) {
        completions.push(...res.items);
        isIncomplete = isIncomplete || res.isIncomplete;
      }
    }
  }

  return { items: completions, isIncomplete };
}
