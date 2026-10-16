/* Copyright 2026 Marimo. All rights reserved. */

import { LanguageServerClient } from "@marimo-team/codemirror-languageserver";
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
    signal?: AbortSignal,
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
  private pendingChange: DidChangeTextDocumentParams | undefined;
  private completionController: AbortController | undefined;
  private openDocumentCount = 0;
  private lastOpenedDocument: DidOpenTextDocumentParams | undefined;
  private copilotSettings: Record<string, unknown> = {};

  public constructor(
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
  public async reInitialize(): Promise<void> {
    logger.log("#reInitialize: Re-initializing LSP connection");
    this.completionController?.abort();
    this.initializePromise = this.initialize();
    await this.initializePromise;
    await this.sendConfiguration();
    this.applyPendingChange();
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
    signal?: AbortSignal,
  ): Promise<LSPRequestMap[Method][1]> {
    assertHasLanguageServerRpc(this);
    return (await this.request(
      method,
      params,
      REQUEST_TIMEOUT_MS,
      signal,
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

  public override getInitializationOptions() {
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

  public override async textDocumentDidOpen(
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

  public override async textDocumentDidClose(
    params: DidCloseTextDocumentParams,
  ): Promise<void> {
    if (this.openDocumentCount === 0) {
      return;
    }
    this.openDocumentCount--;
    if (this.openDocumentCount === 0) {
      this.pendingChange = undefined;
      this.completionController?.abort();
    }
    return super.textDocumentDidClose(params);
  }

  public override async textDocumentCompletion(
    params: CompletionParams,
  ): Promise<CompletionList | CompletionItem[]> {
    // Not used in Copilot
    return [];
  }

  public override async textDocumentDidChange(
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

    this.completionController?.abort();
    this.pendingChange = {
      ...params,
      textDocument: VersionedTextDocumentIdentifier.create(
        params.textDocument.uri,
        ++this.documentVersion,
      ),
    };
  }

  private applyPendingChange(): DidChangeTextDocumentParams | undefined {
    const pending = this.pendingChange;
    if (!pending) {
      return;
    }
    this.pendingChange = undefined;
    const text = getCodes(pending.contentChanges[0].text);
    this.lastOpenedDocument = {
      textDocument: {
        ...pending.textDocument,
        languageId:
          this.lastOpenedDocument?.textDocument.languageId ??
          DEFAULT_LANGUAGE_ID,
        text,
      },
    };
    return { ...pending, contentChanges: [{ text }] };
  }

  /** Assemble and send the latest notebook once, just before requesting a suggestion. */
  public async flushDocumentChanges(currentCode?: string): Promise<string> {
    // Another cell may have changed since the focused editor last typed.
    // The focused cell must be last in the shared document for cursor mapping.
    if (
      currentCode !== undefined &&
      this.lastOpenedDocument &&
      this.pendingChange?.contentChanges[0].text !== currentCode
    ) {
      this.pendingChange = {
        textDocument: VersionedTextDocumentIdentifier.create(
          this.lastOpenedDocument.textDocument.uri,
          ++this.documentVersion,
        ),
        contentChanges: [{ text: currentCode }],
      };
    }
    const pending = this.pendingChange;
    const change = this.applyPendingChange();
    if (change) {
      try {
        await super.textDocumentDidChange(change);
      } catch (error) {
        // Preserve newer edits if the send failed while another change arrived.
        this.pendingChange ??= pending;
        throw error;
      }
    }
    return this.lastOpenedDocument?.textDocument.text ?? "";
  }

  public override textDocumentHover(params: HoverParams): Promise<Hover> {
    // Not used in Copilot
    return Promise.resolve({ contents: [] });
  }

  // AUTH
  public signOut() {
    return this._request("signOut", {});
  }

  public async signInInitiate() {
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

  public async signInConfirm(params: GitHubCopilotSignInConfirmParams) {
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

  public async signedIn() {
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

  public async getCompletion(
    params: InlineCompletionParams,
    signal?: AbortSignal,
  ): Promise<InlineCompletionList | InlineCompletionItem[] | null> {
    if (this.isDisabled() || signal?.aborted || this.openDocumentCount === 0) {
      return null;
    }

    this.completionController?.abort();
    const controller = new AbortController();
    this.completionController = controller;
    const abort = () => controller.abort();
    signal?.addEventListener("abort", abort, { once: true });
    const requestVersion = this.documentVersion;
    setGitHubCopilotLoadingVersion(requestVersion);
    try {
      await this.flushDocumentChanges();
      if (
        controller.signal.aborted ||
        this.isDisabled() ||
        requestVersion === 0
      ) {
        return null;
      }
      const response = await this._request(
        "textDocument/inlineCompletion",
        {
          ...params,
          textDocument: VersionedTextDocumentIdentifier.create(
            params.textDocument.uri,
            requestVersion,
          ),
        },
        controller.signal,
      );
      if (
        controller.signal.aborted ||
        this.isDisabled() ||
        requestVersion !== this.documentVersion
      ) {
        return null;
      }
      return response;
    } catch (error) {
      if (!controller.signal.aborted) {
        logger.warn("#getCompletion: Failed to fetch completions", error);
      }
      return null;
    } finally {
      signal?.removeEventListener("abort", abort);
      // A superseded request can have the same document version as its successor.
      if (this.completionController === controller) {
        this.completionController = undefined;
        clearGitHubCopilotLoadingVersion(requestVersion);
      }
    }
  }

  public override close(): void {
    this.pendingChange = undefined;
    this.completionController?.abort();
    super.close();
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
