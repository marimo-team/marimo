/* Copyright 2024 Marimo. All rights reserved. */

import type { LanguageServerPlugin } from "@marimo-team/codemirror-languageserver";
import type * as LSP from "vscode-languageserver-protocol";
import { Objects } from "@/utils/objects";
import type { ILanguageServerClient } from "./types";
import { getLSPDocument } from "./utils.ts";

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
    this.documentUri = getLSPDocument();
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
      .filter((c) => c != null);

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
      .filter((c) => c !== null);
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

  private firstWithCapability(
    capability: keyof LSP.ServerCapabilities,
  ): ILanguageServerClient | undefined {
    return this.clients.find((client) => client.capabilities?.[capability]);
  }

  private clientsWithCapability(
    capability: keyof LSP.ServerCapabilities,
  ): ILanguageServerClient[] {
    return this.clients.filter((client) => client.capabilities?.[capability]);
  }

  async initialize(): Promise<void> {
    await Promise.all(this.clients.map((client) => client.initialize()));
  }

  async close(): Promise<void> {
    await Promise.all(this.clients.map((client) => client.close()));
  }

  async textDocumentDidChange(
    params: LSP.DidChangeTextDocumentParams,
  ): Promise<LSP.DidChangeTextDocumentParams> {
    await Promise.all(
      this.clients.map((client) => client.textDocumentDidChange(params)),
    );

    return params;
  }

  async completionItemResolve(
    item: LSP.CompletionItem,
  ): Promise<LSP.CompletionItem> {
    const client = this.firstWithCapability("completionProvider");
    if (client) {
      return client.completionItemResolve(item);
    }
    return item;
  }

  async textDocumentCodeAction(
    params: LSP.CodeActionParams,
  ): Promise<Array<LSP.Command | LSP.CodeAction> | null> {
    const client = this.firstWithCapability("codeActionProvider");
    if (client) {
      return client.textDocumentCodeAction(params);
    }
    return null;
  }

  async textDocumentRename(
    params: LSP.RenameParams,
  ): Promise<LSP.WorkspaceEdit | null> {
    const client = this.firstWithCapability("renameProvider");
    if (client) {
      return client.textDocumentRename(params);
    }
    return null;
  }

  async textDocumentPrepareRename(
    params: LSP.PrepareRenameParams,
  ): Promise<LSP.PrepareRenameResult | null> {
    const client = this.firstWithCapability("renameProvider");
    if (client) {
      return client.textDocumentPrepareRename(params);
    }
    return null;
  }

  async textDocumentSignatureHelp(
    params: LSP.SignatureHelpParams,
  ): Promise<LSP.SignatureHelp | null> {
    const client = this.firstWithCapability("signatureHelpProvider");
    if (client) {
      return client.textDocumentSignatureHelp(params);
    }
    return null;
  }

  attachPlugin(plugin: LanguageServerPlugin): void {
    this.clients.forEach((client) => client.attachPlugin(plugin));
  }

  detachPlugin(plugin: LanguageServerPlugin): void {
    this.clients.forEach((client) => client.detachPlugin(plugin));
  }

  // Merge completions from all clients
  async textDocumentCompletion(
    params: LSP.CompletionParams,
  ): Promise<LSP.CompletionList | LSP.CompletionItem[] | null> {
    const clients = this.clientsWithCapability("completionProvider");
    const results = await Promise.allSettled(
      clients.map((client) => client.textDocumentCompletion(params)),
    );

    return mergeCompletions(results);
  }

  async textDocumentDefinition(
    params: LSP.DefinitionParams,
  ): Promise<LSP.Definition | LSP.LocationLink[] | null> {
    const client = this.firstWithCapability("definitionProvider");
    if (client) {
      return client.textDocumentDefinition(params);
    }
    return null;
  }

  async textDocumentDidOpen(params: LSP.DidOpenTextDocumentParams) {
    await Promise.all(
      this.clients.map((client) => client.textDocumentDidOpen(params)),
    );

    return params;
  }

  async textDocumentHover(params: LSP.HoverParams): Promise<LSP.Hover> {
    for (const client of this.clients) {
      if (!client.capabilities?.hoverProvider) {
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
  results: Array<
    PromiseSettledResult<LSP.CompletionList | LSP.CompletionItem[] | null>
  >,
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
