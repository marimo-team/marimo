/* Copyright 2023 Marimo. All rights reserved. */
import {
  CompletionItem,
  CompletionList,
  CompletionParams,
  DidChangeTextDocumentParams,
  DidOpenTextDocumentParams,
  HoverParams,
  VersionedTextDocumentIdentifier,
} from "vscode-languageserver-protocol";

import { LanguageServerClient } from "codemirror-languageserver";
import {
  CopilotStatus,
  CopilotSignInInitiateParams,
  CopilotSignInInitiateResult,
  CopilotSignInConfirmParams,
  CopilotSignInConfirmResult,
  CopilotSignOutParams,
  CopilotSignOutResult,
  CopilotGetCompletionsParams,
  CopilotGetCompletionsResult,
  CopilotAcceptCompletionParams,
  CopilotRejectCompletionParams,
} from "./types";
import { isCopilotEnabled } from "./state";

// A map of request methods and their parameters and return types
export interface LSPRequestMap {
  checkStatus: [{}, { status: CopilotStatus }];
  signInInitiate: [CopilotSignInInitiateParams, CopilotSignInInitiateResult];
  signInConfirm: [CopilotSignInConfirmParams, CopilotSignInConfirmResult];
  signOut: [CopilotSignOutParams, CopilotSignOutResult];
  notifyAccepted: [CopilotAcceptCompletionParams, unknown];
  notifyRejected: [CopilotRejectCompletionParams, unknown];
  getCompletions: [CopilotGetCompletionsParams, CopilotGetCompletionsResult];
  "textDocument/completion": [
    CompletionParams,
    CompletionList | CompletionItem[]
  ];
}

export interface LSPNotificationMap {
  "textDocument/didOpen": [DidOpenTextDocumentParams, void];
  "textDocument/didChange": [DidChangeTextDocumentParams, void];
  "textDocument/hover": [HoverParams, void];
}

/**
 * A client for the Copilot language server.
 */
export class CopilotLanguageServerClient extends LanguageServerClient {
  private documentVersion = 0;

  private _request<Method extends keyof LSPRequestMap>(
    method: Method,
    params: LSPRequestMap[Method][0]
  ): Promise<LSPRequestMap[Method][1]> {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (this as any).request(method, params);
  }

  private _notify<Method extends keyof LSPNotificationMap>(
    method: Method,
    params: LSPNotificationMap[Method][0]
  ): void {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (this as any).notify(method, params);
  }

  private isEnabled() {
    return isCopilotEnabled();
  }

  override async textDocumentDidOpen(
    params: DidOpenTextDocumentParams
  ): Promise<DidOpenTextDocumentParams> {
    if (this.isEnabled()) {
      return params;
    }
    await this._notify("textDocument/didOpen", params);
    return params;
  }

  override async textDocumentCompletion(
    params: CompletionParams
  ): Promise<CompletionList | CompletionItem[]> {
    if (this.isEnabled()) {
      return [];
    }
    return this._request("textDocument/completion", params);
  }

  override async textDocumentDidChange(
    params: DidChangeTextDocumentParams
  ): Promise<DidChangeTextDocumentParams> {
    if (this.isEnabled()) {
      return params;
    }
    await this._notify("textDocument/didChange", params);
    return params;
  }

  // AUTH
  signOut() {
    return this._request("signOut", {});
  }

  signInInitiate() {
    return this._request("signInInitiate", {});
  }

  signInConfirm(params: CopilotSignInConfirmParams) {
    return this._request("signInConfirm", params);
  }

  async signedIn() {
    const { status } = await this._request("checkStatus", {});
    return (
      status === "SignedIn" || status === "AlreadySignedIn" || status === "OK"
    );
  }

  // COMPLETIONS
  acceptCompletion(params: CopilotAcceptCompletionParams) {
    return this._request("notifyAccepted", params);
  }

  rejectCompletions(params: CopilotRejectCompletionParams) {
    return this._request("notifyRejected", params);
  }

  async getCompletion(params: CopilotGetCompletionsParams) {
    await super.initializePromise;
    const version = this.documentVersion++;

    await (version === 0
      ? this._notify("textDocument/didOpen", {
          textDocument: {
            uri: params.doc.uri,
            languageId: params.doc.languageId,
            version: version,
            text: params.doc.source,
          },
        })
      : this._notify("textDocument/didChange", {
          textDocument: VersionedTextDocumentIdentifier.create(
            params.doc.uri,
            version
          ),
          contentChanges: [{ text: params.doc.source }],
        }));

    return this._request("getCompletions", {
      doc: {
        ...params.doc,
        version: version,
      },
    });
  }
}
