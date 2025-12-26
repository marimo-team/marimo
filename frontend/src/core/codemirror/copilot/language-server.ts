/* Copyright 2026 Marimo. All rights reserved. */

import { LanguageServerClient } from "@marimo-team/codemirror-languageserver";
import { throttle } from "lodash-es";
import type {
  CompletionItem,
  CompletionList,
  CompletionParams,
  DidChangeTextDocumentParams,
  DidOpenTextDocumentParams,
  Hover,
  HoverParams,
  InlineCompletionItem,
  InlineCompletionList,
  InlineCompletionParams,
} from "vscode-languageserver-protocol";
import { VersionedTextDocumentIdentifier } from "vscode-languageserver-protocol";
import { store } from "@/core/state/jotai";
import { Logger } from "@/utils/Logger";
import { getCodes } from "./getCodes";
import {
  clearGitHubCopilotLoadingVersion,
  copilotStatusState,
  isCopilotEnabled,
  setGitHubCopilotLoadingVersion,
} from "./state";
import type {
  GitHubCopilotSignInConfirmParams,
  GitHubCopilotSignInInitiateResult,
  GitHubCopilotStatusNotificationParams,
  GitHubCopilotStatusResult,
} from "./types";

const logger = Logger.get("@github/copilot-language-server");

// A map of request methods and their parameters and return types
export interface LSPRequestMap {
  checkStatus: [{}, GitHubCopilotStatusResult];
  signIn: [{}, GitHubCopilotSignInInitiateResult];
  signInConfirm: [GitHubCopilotSignInConfirmParams, GitHubCopilotStatusResult];
  signOut: [{}, GitHubCopilotStatusResult];
  "textDocument/inlineCompletion": [
    InlineCompletionParams,
    InlineCompletionList | InlineCompletionItem[] | null,
  ];
}

export interface LSPEventMap {
  statusNotification: GitHubCopilotStatusNotificationParams;
  didChangeStatus: GitHubCopilotStatusNotificationParams;
  "window/logMessage": { type: number; message: string };
}

export type EnhancedNotification = {
  [key in keyof LSPEventMap]: {
    jsonrpc: "2.0";
    id?: null | undefined;
    method: key;
    params: LSPEventMap[key];
  };
}[keyof LSPEventMap];

/**
 * A client for the Copilot language server.
 */
export class CopilotLanguageServerClient extends LanguageServerClient {
  private documentVersion = 0;
  private hasOpenedDocument = false;
  private copilotSettings: Record<string, unknown> = {};

  constructor(
    options: ConstructorParameters<typeof LanguageServerClient>[0] & {
      copilotSettings?: Record<string, unknown>;
    },
  ) {
    super(options);
    this.copilotSettings = options.copilotSettings ?? {};
    this.onNotification(this.handleNotification);
    this.attachInitializeListener();
  }

  private attachInitializeListener() {
    // Send configuration after initialization
    this.initializePromise.then(() => {
      this.sendConfiguration();
    });
  }

  private async sendConfiguration() {
    const settings = this.copilotSettings;
    // Skip if no settings are provided
    if (!settings || Object.keys(settings).length === 0) {
      return;
    }
    await this.notify("workspace/didChangeConfiguration", { settings });
    logger.debug("#sendConfiguration: Configuration sent", settings);
  }

  private async _request<Method extends keyof LSPRequestMap>(
    method: Method,
    params: LSPRequestMap[Method][0],
  ): Promise<LSPRequestMap[Method][1]> {
    return await (
      this as unknown as {
        request: (
          method: Method,
          params: LSPRequestMap[Method][0],
        ) => Promise<LSPRequestMap[Method][1]>;
      }
    ).request(method, params);
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  override async notify(method: any, params: any): Promise<any> {
    logger.debug("#notify", method, params);
    return super.notify(method, params);
  }

  override getInitializationOptions() {
    const info = {
      name: "marimo",
      version: "0.1.0",
    };
    return {
      ...super.getInitializationOptions(),
      workspaceFolders: [],
      capabilities: {
        workspace: { workspaceFolders: false },
      },
      initializationOptions: {
        editorInfo: info,
        editorPluginInfo: info,
      },
    };
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
    this.hasOpenedDocument = true;
    return super.textDocumentDidOpen(params);
  }

  override async textDocumentCompletion(
    params: CompletionParams,
  ): Promise<CompletionList | CompletionItem[]> {
    // Not used in Copilot
    return [];
  }

  override async textDocumentDidChange(
    params: DidChangeTextDocumentParams,
  ): Promise<DidChangeTextDocumentParams> {
    if (this.isDisabled()) {
      return params;
    }

    if (!this.hasOpenedDocument) {
      await this.textDocumentDidOpen({
        textDocument: {
          uri: params.textDocument.uri,
          languageId: "python",
          version: params.textDocument.version,
          text: params.contentChanges[0].text,
        },
      });
    }

    const changes = params.contentChanges;
    if (changes.length !== 1) {
      logger.warn(
        "#textDocumentDidChange: Multiple changes detected. This is not supported.",
        changes,
      );
    }
    const change = changes[0];
    if ("range" in change) {
      logger.warn(
        "#textDocumentDidChange: Copilot doesn't support range changes.",
        change,
      );
    }

    const text = getCodes(change.text);
    return super.textDocumentDidChange({
      ...params,
      contentChanges: [{ text: text }],
      textDocument: VersionedTextDocumentIdentifier.create(
        params.textDocument.uri,
        ++this.documentVersion,
      ),
    });
  }

  override textDocumentHover(params: HoverParams): Promise<Hover> {
    // Not used in Copilot
    return Promise.resolve({ contents: [] });
  }

  // AUTH
  signOut() {
    return this._request("signOut", {});
  }

  async signInInitiate() {
    logger.log("#signInInitiate: Starting sign-in flow");
    try {
      const result = await this._request("signIn", {});
      logger.log("#signInInitiate: Sign-in flow started successfully");
      return result;
    } catch (error) {
      logger.warn("#signInInitiate: Failed to start sign-in flow", error);
      throw error;
    }
  }

  async signInConfirm(params: GitHubCopilotSignInConfirmParams) {
    logger.log("#signInConfirm: Confirming sign-in");
    try {
      const result = await this._request("signInConfirm", params);
      logger.log("#signInConfirm: Sign-in confirmed successfully");
      return result;
    } catch (error) {
      logger.warn("#signInConfirm: Failed to confirm sign-in", error);
      throw error;
    }
  }

  async signedIn() {
    try {
      const { status } = await this._request("checkStatus", {});
      logger.log("#checkStatus: Status check completed", { status });
      return (
        status === "SignedIn" || status === "AlreadySignedIn" || status === "OK"
      );
    } catch (error) {
      logger.warn("#signedIn: Failed to check sign-in status", error);
      throw error;
    }
  }

  private getCompletionInternal = async (
    params: InlineCompletionParams,
    version: number,
  ): Promise<InlineCompletionList | InlineCompletionItem[] | null> => {
    return await this._request("textDocument/inlineCompletion", {
      ...params,
      textDocument: {
        ...params.textDocument,
        version: version,
      } as VersionedTextDocumentIdentifier,
    });
  };

  // Even though the copilot extension has a debounce,
  // there are multiple requests sent at the same time
  // when multiple Codemirror instances are mounted at the same time.
  // So we throttle it to ignore multiple requests at the same time.
  private throttledGetCompletionInternal = throttle(
    this.getCompletionInternal,
    200,
  );

  async getCompletion(
    params: InlineCompletionParams,
  ): Promise<InlineCompletionList | InlineCompletionItem[] | null> {
    if (this.isDisabled()) {
      return null;
    }

    const requestVersion = this.documentVersion;
    (params.textDocument as VersionedTextDocumentIdentifier).version =
      requestVersion;

    // If version is 0, it means the document hasn't been opened yet
    if (requestVersion === 0) {
      return null;
    }

    // Start a loading indicator
    setGitHubCopilotLoadingVersion(requestVersion);
    const response = await this.throttledGetCompletionInternal(
      params,
      requestVersion,
    );
    // Stop the loading indicator (only if the version hasn't changed)
    clearGitHubCopilotLoadingVersion(requestVersion);

    // If the document version has changed since the request was made, return an empty response
    if (requestVersion !== this.documentVersion) {
      return null;
    }

    return response ?? null;
  }

  /**
   * Handle notifications from the Copilot language server.
   * Uses onNotification to listen for statusNotification, didChangeStatus, and window/logMessage.
   */
  private handleNotification: Parameters<
    LanguageServerClient["onNotification"]
  >[0] = (notif) => {
    if (!notif.params) {
      return;
    }

    const notification = notif as unknown as EnhancedNotification;

    // Handle statusNotification
    if (notification.method === "statusNotification") {
      store.set(copilotStatusState, notification.params);
    }

    // Handle didChangeStatus
    if (notification.method === "didChangeStatus") {
      store.set(copilotStatusState, notification.params);
    }

    // Handle window/logMessage
    if (notification.method === "window/logMessage") {
      const params = notification.params as { type: number; message: string };
      const { type, message } = params;
      // Map LSP log types to console methods
      // type: 1 = Error, 2 = Warning, 3 = Info, 4 = Log
      switch (type) {
        case 1: // Error
          logger.error("[GitHub Copilot]", message);
          break;
        case 2: // Warning
          logger.warn("[GitHub Copilot]", message);
          break;
        case 3: // Info
          logger.debug("[GitHub Copilot]", message);
          break;
        default: // Log (type 4 and others)
          logger.log("[GitHub Copilot]", message);
          break;
      }
    }
  };
}
