/* Copyright 2026 Marimo. All rights reserved. */

import { LanguageServerClient } from "@marimo-team/codemirror-languageserver";
import { throttle } from "lodash-es";
import type {
  CompletionItem,
  CompletionList,
  CompletionParams,
  DidChangeTextDocumentParams,
  DidCloseTextDocumentParams,
  DidOpenTextDocumentParams,
  Hover,
  HoverParams,
  InlineCompletionItem,
  InlineCompletionList,
  InlineCompletionParams,
} from "vscode-languageserver-protocol";
import { VersionedTextDocumentIdentifier } from "vscode-languageserver-protocol";
import { store } from "@/core/state/jotai";
import { invariant } from "@/utils/invariant";
import { Logger } from "@/utils/Logger";
import { hasFunctionProperty, isRecord } from "@/utils/records";
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
import type { LanguageAdapterType } from "../language/types";

const logger = Logger.get("@github/copilot-language-server");
const REQUEST_TIMEOUT_MS = 10_000;
// Only used for the synthetic didOpen sent when a change arrives before any open
const DEFAULT_LANGUAGE_ID: LanguageAdapterType = "python";
type NoParams = Record<string, never>;

// A map of request methods and their parameters and return types
export interface LSPRequestMap {
  checkStatus: [NoParams, GitHubCopilotStatusResult];
  signIn: [NoParams, GitHubCopilotSignInInitiateResult];
  signInConfirm: [GitHubCopilotSignInConfirmParams, GitHubCopilotStatusResult];
  signOut: [NoParams, GitHubCopilotStatusResult];
  "textDocument/inlineCompletion": [
    InlineCompletionParams,
    InlineCompletionList | InlineCompletionItem[] | null,
  ];
}

interface UntypedLanguageServerMethods {
  request: (
    method: string,
    params: unknown,
    timeout: number,
  ) => Promise<unknown>;
  notify: (method: string, params: unknown) => Promise<void>;
}

/**
 * `LanguageServerClient#request`/`#notify` are protected and generic over the
 * library's own `LSPRequestMap`/`LSPNotifyMap`
 * This asserts the two inherited methods we need are present.
 */
function assertHasLanguageServerRpc(
  value: unknown,
): asserts value is UntypedLanguageServerMethods {
  invariant(
    isRecord(value) &&
      hasFunctionProperty(value, "request") &&
      hasFunctionProperty(value, "notify"),
    "LanguageServerClient is missing request/notify",
  );
}

/**
 * Normalizes rather than validates: Copilot omits `message`/`busy` on most
 * notifications and ships `kind` values we don't know about, so rejecting on an
 * exact shape match would silently freeze the status indicator.
 */
function parseCopilotStatusNotificationParams(
  value: unknown,
): GitHubCopilotStatusNotificationParams | null {
  if (!isRecord(value)) {
    return null;
  }
  const { busy, kind, message, status } = value;
  return {
    busy: typeof busy === "boolean" ? busy : false,
    kind: typeof kind === "string" ? kind : null,
    message: typeof message === "string" ? message : null,
    status: typeof status === "string" ? status : undefined,
  };
}

function isLogMessageParams(
  value: unknown,
): value is { type: number; message: string } {
  return (
    isRecord(value) &&
    typeof value.type === "number" &&
    typeof value.message === "string"
  );
}

/**
 * A client for the Copilot language server.
 */
export class CopilotLanguageServerClient extends LanguageServerClient {
  private documentVersion = 0;
  private openDocumentCount = 0;
  private lastOpenedDocument: DidOpenTextDocumentParams | undefined;
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
    void this.initializePromise
      .then(() => this.sendConfiguration())
      .catch((error: unknown) => {
        logger.warn("#initialize: Failed to send configuration", error);
      });
  }

  /**
   * Re-run the LSP initialize handshake and send configuration.
   * Called by the transport's onReconnect callback after reconnecting.
   */
  async reInitialize(): Promise<void> {
    logger.log("#reInitialize: Re-initializing LSP connection");
    this.initializePromise = this.initialize();
    await this.initializePromise;
    await this.sendConfiguration();
    if (this.openDocumentCount > 0 && this.lastOpenedDocument) {
      await this.sendNotification(
        "textDocument/didOpen",
        this.lastOpenedDocument,
      );
    }
  }

  private async sendConfiguration() {
    const settings = this.copilotSettings;
    // Skip if no settings are provided
    if (!settings || Object.keys(settings).length === 0) {
      return;
    }
    await this.sendNotification("workspace/didChangeConfiguration", {
      settings,
    });
    logger.debug("#sendConfiguration: Configuration sent", settings);
  }

  private async _request<Method extends keyof LSPRequestMap>(
    method: Method,
    params: LSPRequestMap[Method][0],
  ): Promise<LSPRequestMap[Method][1]> {
    assertHasLanguageServerRpc(this);
    return (await this.request(
      method,
      params,
      REQUEST_TIMEOUT_MS,
    )) as LSPRequestMap[Method][1];
  }

  private async sendNotification(
    method: string,
    params: unknown,
  ): Promise<void> {
    logger.debug("#notify", method, params);
    assertHasLanguageServerRpc(this);
    return this.notify(method, params);
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
  ): Promise<boolean> {
    if (this.isDisabled()) {
      return false;
    }
    this.openDocumentCount++;
    this.lastOpenedDocument = params;
    this.documentVersion = Math.max(
      this.documentVersion,
      params.textDocument.version,
    );
    return super.textDocumentDidOpen(params);
  }

  override async textDocumentDidClose(
    params: DidCloseTextDocumentParams,
  ): Promise<void> {
    if (this.openDocumentCount === 0) {
      return;
    }
    this.openDocumentCount--;
    return super.textDocumentDidClose(params);
  }

  override async textDocumentCompletion(
    params: CompletionParams,
  ): Promise<CompletionList | CompletionItem[]> {
    // Not used in Copilot
    return [];
  }

  override async textDocumentDidChange(
    params: DidChangeTextDocumentParams,
  ): Promise<void> {
    if (this.isDisabled()) {
      return;
    }

    const change = params.contentChanges[0];
    if (!change) {
      logger.warn(
        "#textDocumentDidChange: Ignoring an update with no content changes.",
        params,
      );
      return;
    }

    if (this.openDocumentCount === 0) {
      await this.textDocumentDidOpen({
        textDocument: {
          uri: params.textDocument.uri,
          languageId: DEFAULT_LANGUAGE_ID,
          version: params.textDocument.version,
          text: change.text,
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
    if ("range" in change) {
      logger.warn(
        "#textDocumentDidChange: Copilot doesn't support range changes.",
        change,
      );
    }

    const text = getCodes(change.text);
    const version = ++this.documentVersion;
    // `reInitialize` replays this as a didOpen, so keep the original languageId
    this.lastOpenedDocument = {
      textDocument: {
        uri: params.textDocument.uri,
        languageId:
          this.lastOpenedDocument?.textDocument.languageId ??
          DEFAULT_LANGUAGE_ID,
        version,
        text,
      },
    };
    return super.textDocumentDidChange({
      ...params,
      contentChanges: [{ text: text }],
      textDocument: VersionedTextDocumentIdentifier.create(
        params.textDocument.uri,
        version,
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
        ...VersionedTextDocumentIdentifier.create(
          params.textDocument.uri,
          version,
        ),
      },
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

    // If version is 0, it means the document hasn't been opened yet
    if (requestVersion === 0) {
      return null;
    }

    // Start a loading indicator
    setGitHubCopilotLoadingVersion(requestVersion);
    let response: InlineCompletionList | InlineCompletionItem[] | null;
    try {
      response = await this.throttledGetCompletionInternal(
        {
          ...params,
          textDocument: VersionedTextDocumentIdentifier.create(
            params.textDocument.uri,
            requestVersion,
          ),
        },
        requestVersion,
      );
    } catch (error) {
      // A suggestion that times out should fail quietly rather than surface as
      // an unhandled rejection out of the inline-completion fetcher.
      logger.warn("#getCompletion: Failed to fetch completions", error);
      return null;
    } finally {
      // Stop the loading indicator (only if the version hasn't changed)
      clearGitHubCopilotLoadingVersion(requestVersion);
    }

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
  private handleNotification = (notification: unknown): void => {
    if (!isRecord(notification) || typeof notification.method !== "string") {
      return;
    }

    if (
      notification.method === "statusNotification" ||
      notification.method === "didChangeStatus"
    ) {
      const status = parseCopilotStatusNotificationParams(notification.params);
      if (status) {
        store.set(copilotStatusState, status);
      } else {
        logger.warn(
          "#statusNotification: Ignoring a status update with no params",
          notification.params,
        );
      }
      return;
    }

    if (
      notification.method === "window/logMessage" &&
      isLogMessageParams(notification.params)
    ) {
      const { type, message } = notification.params;
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
