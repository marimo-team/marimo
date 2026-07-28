/* Copyright 2026 Marimo. All rights reserved. */

import {
  type JSONRPCMessage,
  type Transport,
  WebSocketTransport,
} from "@marimo-team/codemirror-languageserver";
import { Logger } from "@/utils/Logger";

const MAX_PENDING_MESSAGES = 1000;
const RESYNCED_NOTIFICATION_METHODS = new Set([
  "textDocument/didOpen",
  "textDocument/didChange",
  "textDocument/didClose",
]);
const RESTORATION_METHODS = new Set([
  "initialize",
  "initialized",
  "workspace/didChangeConfiguration",
  "textDocument/didOpen",
]);

export interface ReconnectingWebSocketTransportOptions {
  /**
   * Function that returns the WebSocket URL to connect to.
   */
  getWsUrl: () => string;

  /**
   * Optional function to wait for before attempting to connect.
   * This is useful for ensuring dependencies (like the runtime) are ready.
   */
  waitForConnection?: () => Promise<void>;

  /**
   * Optional callback that is called after a successful reconnection.
   * This allows the LSP client to re-synchronize state (e.g., re-send document open notifications).
   */
  onReconnect?: () => Promise<void>;

  /**
   * Number of connection attempts in each retry cycle.
   * @default 1
   */
  retries?: number;

  /**
   * Delay between connection attempts.
   * @default 1000
   */
  retryDelayMs?: number;

  /**
   * Called when every connection attempt in a retry cycle fails.
   */
  onConnectionFailure?: (error: Error) => void;
}

/**
 * A WebSocket transport that automatically reconnects when the connection is
 * lost. Messages produced while reconnecting are replayed only after the LSP
 * client has re-initialized and restored its document state.
 *
 * Deliberately does not implement the optional `Transport.onClose`: JSONRPCClient
 * latches the first close error and never clears it, so forwarding drops would
 * fail every later request instead of surviving a reconnect.
 */
export class ReconnectingWebSocketTransport implements Transport {
  private delegate: WebSocketTransport | undefined;
  private connectionPromise: Promise<void> | undefined;
  private isDelegateConnected = false;
  /**
   * Identifies the current connection attempt. Bumping it abandons whatever is
   * in flight: an attempt whose socket has already died may stay parked on an
   * LSP request timeout, and it must neither delay recovery nor mutate state
   * belonging to the attempt that replaced it.
   */
  private connectionGeneration = 0;
  /** Generation currently restoring LSP state, if any. */
  private restoringGeneration: number | undefined;
  private isClosed = false;
  private hasConnectedBefore = false;
  private readonly messageHandlers = new Set<
    (message: JSONRPCMessage) => void
  >();
  private pendingMessages: JSONRPCMessage[] = [];
  /**
   * Backlog detached by the in-flight attempt. Held here rather than in a local
   * so that abandoning that attempt can hand the messages straight back to the
   * queue instead of stranding them until it eventually settles.
   */
  private inFlightBacklog: JSONRPCMessage[] | undefined;
  private hasLoggedQueueOverflow = false;
  private disposeDelegateMessage: (() => void) | undefined;
  private disposeDelegateClose: (() => void) | undefined;
  private readonly options: Required<
    Pick<ReconnectingWebSocketTransportOptions, "retries" | "retryDelayMs">
  > &
    Omit<ReconnectingWebSocketTransportOptions, "retries" | "retryDelayMs">;

  public onReconnect: (() => Promise<void>) | undefined;

  constructor(options: ReconnectingWebSocketTransportOptions) {
    this.options = {
      ...options,
      retries: options.retries ?? 1,
      retryDelayMs: options.retryDelayMs ?? 1000,
    };
    this.onReconnect = options.onReconnect;
  }

  async connect(): Promise<void> {
    if (this.isClosed) {
      throw new Error("Transport is closed");
    }
    if (this.isDelegateConnected) {
      return;
    }
    if (this.connectionPromise) {
      return this.connectionPromise;
    }

    const generation = ++this.connectionGeneration;
    const promise = this.connectWithRetries(generation).finally(() => {
      // An abandoned attempt must not clear its successor's promise.
      if (this.connectionPromise === promise) {
        this.connectionPromise = undefined;
      }
    });
    this.connectionPromise = promise;
    return promise;
  }

  /** Whether `generation` has been superseded or the transport was closed. */
  private isStale(generation: number): boolean {
    return this.isClosed || generation !== this.connectionGeneration;
  }

  send(message: JSONRPCMessage): void {
    if (this.isClosed) {
      return;
    }
    if (
      this.delegate &&
      this.isDelegateConnected &&
      (this.restoringGeneration === undefined ||
        this.canSendWhileRestoring(message))
    ) {
      this.delegate.send(message);
      return;
    }

    if (this.pendingMessages.length < MAX_PENDING_MESSAGES) {
      this.pendingMessages.push(message);
    } else if (!this.hasLoggedQueueOverflow) {
      // Log once per episode; the queue fills one keystroke at a time.
      this.hasLoggedQueueOverflow = true;
      Logger.error(
        `LSP reconnect queue is full (${MAX_PENDING_MESSAGES}); dropping messages until it drains`,
      );
    }
    this.reconnect();
  }

  onMessage(handler: (message: JSONRPCMessage) => void): () => void {
    this.messageHandlers.add(handler);
    return () => {
      this.messageHandlers.delete(handler);
    };
  }

  close(): void {
    if (this.isClosed) {
      return;
    }
    this.isClosed = true;
    this.isDelegateConnected = false;
    this.restoringGeneration = undefined;
    // Abandon anything in flight so it cannot touch state after teardown.
    this.connectionGeneration++;
    this.connectionPromise = undefined;
    this.pendingMessages = [];
    this.messageHandlers.clear();
    this.disposeDelegate();
    this.delegate?.close();
    this.delegate = undefined;
  }

  private async connectWithRetries(generation: number): Promise<void> {
    let lastError: Error | undefined;

    for (let attempt = 1; attempt <= this.options.retries; attempt++) {
      try {
        await this.connectDelegate(generation);
        return;
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));
        if (this.isStale(generation)) {
          // Superseded while we were failing; the live attempt owns the
          // delegate now, so tear down nothing and retry nothing.
          throw lastError;
        }
        this.invalidateDelegate();
        Logger.warn(
          `WebSocket connection attempt ${attempt}/${this.options.retries} failed`,
          lastError,
        );

        if (attempt < this.options.retries) {
          await new Promise((resolve) =>
            setTimeout(resolve, this.options.retryDelayMs),
          );
        }
      }
    }

    const error = lastError ?? new Error("WebSocket connection failed");
    this.options.onConnectionFailure?.(error);
    throw error;
  }

  private async connectDelegate(generation: number): Promise<void> {
    await this.options.waitForConnection?.();
    if (this.isStale(generation)) {
      throw new Error("Connection attempt abandoned");
    }

    const delegate = this.createDelegate();
    await delegate.connect();
    if (this.isStale(generation) || this.delegate !== delegate) {
      delegate.close();
      throw new Error("Transport closed while connecting");
    }

    this.isDelegateConnected = true;
    const isReconnection = this.hasConnectedBefore;
    this.hasConnectedBefore = true;

    // Detach before restoring: notifications queued while the socket was down
    // are superseded by what `onReconnect` re-sends, but ones produced *during*
    // restoration are not — they carry edits the restore snapshot never saw,
    // and the notebook snapshotter will not re-emit them.
    const queuedWhileDisconnected = this.detachPendingMessages();
    this.inFlightBacklog = queuedWhileDisconnected;

    try {
      if (isReconnection) {
        this.restoringGeneration = generation;
        try {
          await this.onReconnect?.();
        } finally {
          // Only clear the gate if a newer attempt hasn't taken it over.
          if (this.restoringGeneration === generation) {
            this.restoringGeneration = undefined;
          }
        }
      }

      if (
        this.isStale(generation) ||
        this.delegate !== delegate ||
        !this.isDelegateConnected
      ) {
        throw new Error("WebSocket closed while restoring LSP state");
      }
    } catch (error) {
      // Nothing superseded the backlog, so restore it ahead of anything queued
      // since. If this attempt was abandoned, whoever abandoned it already
      // reclaimed the backlog and owns the queue now.
      if (!this.isStale(generation)) {
        this.reclaimInFlightBacklog();
      }
      throw error;
    }

    const replayable =
      isReconnection && this.onReconnect
        ? queuedWhileDisconnected.filter(
            (message) =>
              !(
                "method" in message &&
                RESYNCED_NOTIFICATION_METHODS.has(message.method)
              ),
          )
        : queuedWhileDisconnected;

    this.inFlightBacklog = undefined;
    for (const message of [...replayable, ...this.detachPendingMessages()]) {
      delegate.send(message);
    }

    Logger.log("WebSocket transport connected successfully");
  }

  private detachPendingMessages(): JSONRPCMessage[] {
    const messages = this.pendingMessages;
    this.pendingMessages = [];
    this.hasLoggedQueueOverflow = false;
    return messages;
  }

  /** Return the in-flight attempt's backlog to the front of the queue. */
  private reclaimInFlightBacklog(): void {
    if (!this.inFlightBacklog) {
      return;
    }
    this.pendingMessages = [
      ...this.inFlightBacklog,
      ...this.pendingMessages,
    ].slice(0, MAX_PENDING_MESSAGES);
    this.inFlightBacklog = undefined;
  }

  private canSendWhileRestoring(message: JSONRPCMessage): boolean {
    // Responses to server-initiated requests must not be held or the
    // initialization handshake could deadlock.
    return !("method" in message) || RESTORATION_METHODS.has(message.method);
  }

  private createDelegate(): WebSocketTransport {
    this.invalidateDelegate();

    const delegate = new WebSocketTransport(this.options.getWsUrl());
    this.delegate = delegate;
    this.disposeDelegateMessage = delegate.onMessage((message) => {
      for (const handler of this.messageHandlers) {
        try {
          handler(message);
        } catch (error) {
          Logger.error("LSP message handler failed", error);
        }
      }
    });
    this.disposeDelegateClose = delegate.onClose((error) => {
      if (this.delegate !== delegate || this.isClosed) {
        return;
      }
      Logger.warn("WebSocket transport connection closed", error);
      this.isDelegateConnected = false;
      this.disposeDelegate();
      this.delegate = undefined;
      // Abandon any attempt still in flight: it is bound to the socket that
      // just died and may sit parked on an LSP request timeout. Take its
      // backlog and drop the promise so the next connect() starts immediately
      // rather than joining a doomed one.
      this.restoringGeneration = undefined;
      this.reclaimInFlightBacklog();
      this.connectionPromise = undefined;
      queueMicrotask(() => this.reconnect());
    });
    return delegate;
  }

  private reconnect(): void {
    void this.connect().catch((error) => {
      Logger.error("WebSocket transport reconnection failed", error);
    });
  }

  private invalidateDelegate(): void {
    this.isDelegateConnected = false;
    this.restoringGeneration = undefined;
    this.disposeDelegate();
    this.delegate?.close();
    this.delegate = undefined;
  }

  private disposeDelegate(): void {
    this.disposeDelegateMessage?.();
    this.disposeDelegateMessage = undefined;
    this.disposeDelegateClose?.();
    this.disposeDelegateClose = undefined;
  }
}
