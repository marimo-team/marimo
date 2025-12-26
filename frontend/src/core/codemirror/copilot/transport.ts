/* Copyright 2026 Marimo. All rights reserved. */

import { WebSocketTransport } from "@open-rpc/client-js";
import type { JSONRPCRequestData } from "@open-rpc/client-js/build/Request";
import { Transport } from "@open-rpc/client-js/build/transports/Transport";
import { prettyError } from "@/utils/errors";
import { Logger } from "@/utils/Logger";

export interface LazyWebsocketTransportOptions {
  /**
   * Function that returns the WebSocket URL to connect to.
   */
  getWsUrl: () => string;

  /**
   * Function to wait for before attempting to connect.
   * This ensures all prerequisites (like copilot being enabled and runtime connection) are ready.
   */
  waitForReady: () => Promise<void>;

  /**
   * Function to show error toast notifications.
   */
  showError: (title: string, description: string | React.ReactNode) => void;

  /**
   * Number of retry attempts for connection.
   * @default 3
   */
  retries?: number;

  /**
   * Delay between retry attempts in milliseconds.
   * @default 1000
   */
  retryDelayMs?: number;

  /**
   * Maximum timeout for sendData operations in milliseconds.
   * @default 5000
   */
  maxTimeoutMs?: number;
}

interface Subscription {
  event: "pending" | "notification" | "response" | "error";
  handler: Parameters<Transport["subscribe"]>[1];
}

/**
 * A WebSocket transport that lazily connects after waiting for prerequisites.
 *
 * This transport:
 * - Waits for copilot to be enabled before connecting
 * - Waits for the websocket to be available before connecting
 * - Forwards subscriptions/unsubscriptions to the delegate
 * - Handles reconnection automatically
 */
export class LazyWebsocketTransport extends Transport {
  private delegate: WebSocketTransport | undefined;
  private pendingSubscriptions: Subscription[] = [];
  private readonly options: Required<LazyWebsocketTransportOptions>;

  constructor(options: LazyWebsocketTransportOptions) {
    super();
    this.delegate = undefined;
    this.pendingSubscriptions = [];
    this.options = {
      retries: options.retries ?? 3,
      retryDelayMs: options.retryDelayMs ?? 1000,
      maxTimeoutMs: options.maxTimeoutMs ?? 5000,
      getWsUrl: options.getWsUrl,
      waitForReady: options.waitForReady,
      showError: options.showError,
    };
  }

  override subscribe(...args: Parameters<Transport["subscribe"]>): void {
    // Register handler on parent Transport
    super.subscribe(...args);

    const [event, handler] = args;

    // Track the subscription
    this.pendingSubscriptions.push({ event, handler });

    // Also register on delegate if it exists
    if (this.delegate) {
      this.delegate.subscribe(event, handler);
    }
  }

  override unsubscribe(
    ...args: Parameters<Transport["unsubscribe"]>
  ): import("events").EventEmitter | undefined {
    // Unsubscribe from parent Transport
    const result = super.unsubscribe(...args);

    const [event, handler] = args;
    // Also unsubscribe from delegate if it exists
    if (this.delegate) {
      this.delegate.unsubscribe(event, handler);
    }

    // Remove from pending subscriptions if handler is provided
    if (handler) {
      if (event) {
        // Remove specific handler for specific event
        const index = this.pendingSubscriptions.findIndex(
          (sub) => sub.event === event && sub.handler === handler,
        );
        if (index > -1) {
          this.pendingSubscriptions.splice(index, 1);
        }
      } else {
        // Remove handler from all events
        this.pendingSubscriptions = this.pendingSubscriptions.filter(
          (sub) => sub.handler !== handler,
        );
      }
    } else if (event) {
      // Remove all handlers for specific event
      this.pendingSubscriptions = this.pendingSubscriptions.filter(
        (sub) => sub.event !== event,
      );
    } else {
      // Remove all subscriptions
      this.pendingSubscriptions = [];
    }

    return result;
  }

  private createDelegate(): WebSocketTransport {
    const delegate = new WebSocketTransport(this.options.getWsUrl());
    // Register all pending subscriptions on the delegate
    for (const { event, handler } of this.pendingSubscriptions) {
      delegate.subscribe(event, handler);
    }
    return delegate;
  }

  private async tryConnect(): Promise<void> {
    for (let attempt = 1; attempt <= this.options.retries; attempt++) {
      try {
        // Create delegate, if it doesn't exist
        if (!this.delegate) {
          this.delegate = this.createDelegate();
        }
        await this.delegate.connect();
        Logger.log("Copilot#connect: Connected successfully");
        return;
      } catch (error) {
        Logger.warn(
          `Copilot#connect: Connection attempt ${attempt}/${this.options.retries} failed`,
          error,
        );
        if (attempt === this.options.retries) {
          this.delegate = undefined;
          // Show error toast on final retry
          this.options.showError(
            "GitHub Copilot Connection Error",
            "Failed to connect to GitHub Copilot. Please check your settings and try again.\n\n" +
              prettyError(error),
          );
          throw error;
        }
        await new Promise((resolve) =>
          setTimeout(resolve, this.options.retryDelayMs),
        );
      }
    }
  }

  override async connect(): Promise<void> {
    // Wait for all prerequisites to be ready
    await this.options.waitForReady();

    // Try connecting with retries
    return this.tryConnect();
  }

  override close(): void {
    this.delegate?.close();
    this.delegate = undefined;
  }

  override async sendData(
    data: JSONRPCRequestData,
    timeout: number | null | undefined,
  ): Promise<unknown> {
    // If delegate is undefined, try to reconnect
    if (!this.delegate) {
      Logger.log("Copilot#sendData: Delegate not initialized, reconnecting...");
      try {
        // Ensure prerequisites are ready before attempting connection
        await this.options.waitForReady();
        await this.tryConnect();
      } catch (error) {
        Logger.error("Copilot#sendData: Failed to reconnect transport", error);
        throw new Error(
          "Unable to connect to GitHub Copilot. Please check your settings and try again.",
        );
      }
    }

    // After reconnection, delegate should be initialized
    if (!this.delegate) {
      throw new Error(
        "Failed to initialize GitHub Copilot connection. Please try again.",
      );
    }

    // Clamp timeout to maxTimeoutMs
    timeout = Math.min(
      timeout ?? this.options.maxTimeoutMs,
      this.options.maxTimeoutMs,
    );
    return this.delegate.sendData(data, timeout);
  }
}
