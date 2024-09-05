/* Copyright 2024 Marimo. All rights reserved. */
import type {
  CompletionItem,
  CompletionList,
  CompletionParams,
  DidChangeTextDocumentParams,
  DidOpenTextDocumentParams,
  Hover,
  HoverParams,
} from "vscode-languageserver-protocol";
import { VersionedTextDocumentIdentifier } from "vscode-languageserver-protocol";

import { LanguageServerClient } from "codemirror-languageserver";
import type {
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
import {
  isCopilotEnabled,
  setGitHubCopilotStartLoadingVersion,
  clearGitHubCopilotStopLoadingVersion,
} from "./state";
import { getCodes } from "./getCodes";
import { Logger } from "@/utils/Logger";
import { debounce } from "lodash-es";

// A map of request methods and their parameters and return types
export interface LSPRequestMap {
  checkStatus: [{}, { status: CopilotStatus; user: string }];
  signInInitiate: [CopilotSignInInitiateParams, CopilotSignInInitiateResult];
  signInConfirm: [CopilotSignInConfirmParams, CopilotSignInConfirmResult];
  signOut: [CopilotSignOutParams, CopilotSignOutResult];
  notifyAccepted: [CopilotAcceptCompletionParams, unknown];
  notifyRejected: [CopilotRejectCompletionParams, unknown];
  getCompletions: [CopilotGetCompletionsParams, CopilotGetCompletionsResult];
}

/**
 * A client for the Copilot language server.
 */
export class CopilotLanguageServerClient extends LanguageServerClient {
  private documentVersion = 0;

  private _request<Method extends keyof LSPRequestMap>(
    method: Method,
    params: LSPRequestMap[Method][0],
  ): Promise<LSPRequestMap[Method][1]> {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (this as any).request(method, params);
  }

  private isDisabled() {
    return !isCopilotEnabled();
  }

  override async textDocumentDidOpen(
    params: DidOpenTextDocumentParams,
  ): Promise<DidOpenTextDocumentParams> {
    if (this.isDisabled()) {
      return params;
    }
    return super.textDocumentDidOpen(params);
  }

  override async textDocumentCompletion(
    params: CompletionParams,
  ): Promise<CompletionList | CompletionItem[]> {
    if (this.isDisabled()) {
      return [];
    }
    return super.textDocumentCompletion(params);
  }

  override async textDocumentDidChange(
    params: DidChangeTextDocumentParams,
  ): Promise<DidChangeTextDocumentParams> {
    if (this.isDisabled()) {
      return params;
    }
    return super.textDocumentDidChange({
      ...params,
      contentChanges: [{ text: getCodes(params.contentChanges[0].text) }],
      textDocument: VersionedTextDocumentIdentifier.create(
        params.textDocument.uri,
        ++this.documentVersion,
      ),
    });
  }

  override textDocumentHover(params: HoverParams): Promise<Hover> {
    if (this.isDisabled()) {
      return Promise.resolve({ contents: [] });
    }
    return super.textDocumentHover(params);
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
    const { status, user } = await this._request("checkStatus", {});
    Logger.debug("Copilot#signedIn", status, user);
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

  private async getCompletionInternal(
    params: CopilotGetCompletionsParams,
    version: number,
  ) {
    // Start a loading indicator
    setGitHubCopilotStartLoadingVersion(version);
    const response = await this._request("getCompletions", {
      doc: {
        ...params.doc,
        version: version,
      },
    });
    // Stop the loading indicator (only if the version hasn't changed)
    clearGitHubCopilotStopLoadingVersion(version);

    // If the document version has changed since the request was made, return an empty response
    if (version !== this.documentVersion) {
      return { completions: [] };
    }

    return response;
  }

  // Even though the copilot extension has a debounce,
  // there are multiple requests sent at the same time
  // when multiple Codemirror instances are mounted at the same time.
  private debouncedGetCompletionInternal = debounce(
    this.getCompletionInternal.bind(this),
    300,
  );

  async getCompletion(params: CopilotGetCompletionsParams) {
    if (this.isDisabled()) {
      return { completions: [] };
    }

    const version = this.documentVersion;

    // If version is 0, it means the document hasn't been opened yet
    if (version === 0) {
      return { completions: [] };
    }

    return this.debouncedGetCompletionInternal(params, version);
  }
}
