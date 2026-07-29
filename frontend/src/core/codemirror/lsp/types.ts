/* Copyright 2026 Marimo. All rights reserved. */

import type { LanguageServerClient } from "@marimo-team/codemirror-languageserver";
import type { DocumentUri } from "vscode-languageserver-protocol";
import type { CellId } from "@/core/cells/ids";
import { invariant } from "@/utils/invariant";
import type { TypedString } from "@/utils/typed";

type LanguageServerClientMember =
  | "ready"
  | "capabilities"
  | "initializePromise"
  | "clientCapabilities"
  | "initialize"
  | "close"
  | "hasCapability"
  | "textDocumentDidOpen"
  | "textDocumentDidChange"
  | "textDocumentDidClose"
  | "textDocumentWillSave"
  | "textDocumentWillSaveWaitUntil"
  | "textDocumentDidSave"
  | "textDocumentHover"
  | "textDocumentCompletion"
  | "completionItemResolve"
  | "textDocumentDefinition"
  | "textDocumentCodeAction"
  | "codeActionResolve"
  | "textDocumentRename"
  | "textDocumentPrepareRename"
  | "textDocumentSignatureHelp"
  | "onNotification";

/**
 * The stable client surface used by marimo's notebook and federated adapters.
 * Keeping this explicit prevents unrelated additions to the upstream client
 * from becoming required adapter methods.
 */
export type ILanguageServerClient = Pick<
  LanguageServerClient,
  LanguageServerClientMember
>;

/**
 * LSP request methods that `FederatedLanguageServerClient` routes to whichever
 * child client declares support.
 *
 * This is the subset of `ILanguageServerClient`'s request methods
 * https://github.com/marimo-team/codemirror-languageserver/blob/v2.0.0/src/lsp.ts#L88-L113
 */
export type RoutableLspMethod =
  | "textDocument/hover"
  | "textDocument/completion"
  | "textDocument/definition"
  | "textDocument/codeAction"
  | "textDocument/rename"
  | "textDocument/prepareRename"
  | "textDocument/signatureHelp";

export type CellDocumentUri = DocumentUri & TypedString<"CellDocumentUri">;

export const CellDocumentUri = {
  PREFIX: "file:///",
  of(cellId: CellId): CellDocumentUri {
    return `${this.PREFIX}${cellId}` as CellDocumentUri;
  },
  is(uri: string): uri is CellDocumentUri {
    return uri.startsWith(this.PREFIX);
  },
  parse(uri: string): CellId {
    invariant(this.is(uri), `Invalid cell document URI: ${uri}`);
    return uri.slice(this.PREFIX.length) as CellId;
  },
};

/**
 * Notify is a @protected method on `LanguageServerClient`,
 * hiding public use with TypeScript.
 */
export function isClientWithNotify(
  client: ILanguageServerClient,
): client is ILanguageServerClient & {
  notify: (method: string, params: unknown) => Promise<void>;
} {
  return "notify" in client && typeof client.notify === "function";
}

export interface ClientNotification {
  method: string;
  params: unknown;
}

export function isClientWithProcessNotification(
  client: ILanguageServerClient,
): client is ILanguageServerClient & {
  processNotification: (notification: ClientNotification) => void;
} {
  return (
    "processNotification" in client &&
    typeof client.processNotification === "function"
  );
}
