/* Copyright 2024 Marimo. All rights reserved. */
import { WebSocketTransport } from "@open-rpc/client-js";
import type { JSONRPCRequestData } from "@open-rpc/client-js/build/Request";
import { Transport } from "@open-rpc/client-js/build/transports/Transport";
import { Logger } from "@/utils/Logger";

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
}

/**
 * A WebSocket transport that automatically reconnects when the connection is lost.
 * This handles cases like computer sleep/wake or network interruptions.
 */
export class ReconnectingWebSocketTransport extends Transport {
  private delegate: WebSocketTransport | undefined;
  private readonly options: ReconnectingWebSocketTransportOptions;
  private connectionPromise: Promise<void> | undefined;
  private isClosed = false;

  constructor(options: ReconnectingWebSocketTransportOptions) {
    super();
    this.options = options;
    this.delegate = undefined;
  }

  /**
   * Create a new WebSocket delegate, replacing any existing one.
   */
  private createDelegate(): WebSocketTransport {
    // Close the old delegate if it exists
    if (this.delegate) {
      try {
        this.delegate.close();
      } catch (error) {
        Logger.warn("Error closing old WebSocket delegate", error);
      }
    }

    // Create a new delegate
    this.delegate = new WebSocketTransport(this.options.getWsUrl());
    return this.delegate;
  }

  /**
   * Check if the current delegate's WebSocket is in a closed or closing state.
   */
  private isDelegateClosedOrClosing(): boolean {
    if (!this.delegate) {
      return true;
    }

    // Access the internal connection to check its readyState
    const ws = this.delegate.connection;
    if (!ws) {
      return true;
    }

    // WebSocket.CLOSING = 2, WebSocket.CLOSED = 3
    return (
      ws.readyState === WebSocket.CLOSING || ws.readyState === WebSocket.CLOSED
    );
  }

  override async connect() {
    // Don't reconnect if explicitly closed
    if (this.isClosed) {
      throw new Error("Transport is closed");
    }

    // If already connecting, wait for that connection
    if (this.connectionPromise) {
      return this.connectionPromise;
    }

    this.connectionPromise = (async () => {
      try {
        // Wait for dependencies to be ready (e.g., runtime connection)
        if (this.options.waitForConnection) {
          await this.options.waitForConnection();
        }

        // Create a new delegate if needed
        if (!this.delegate || this.isDelegateClosedOrClosing()) {
          this.createDelegate();
        }

        // Connect the delegate
        await this.delegate!.connect();
        Logger.log("WebSocket transport connected successfully");
      } catch (error) {
        Logger.error("WebSocket transport connection failed", error);
        // Clear the delegate on failure so we create a new one on retry
        this.delegate = undefined;
        throw error;
      } finally {
        this.connectionPromise = undefined;
      }
    })();

    return this.connectionPromise;
  }

  override close() {
    this.isClosed = true;
    this.delegate?.close();
    this.delegate = undefined;
    this.connectionPromise = undefined;
  }

  override async sendData(
    data: JSONRPCRequestData,
    timeout: number | null | undefined,
  ) {
    // If the delegate is closed or closing, try to reconnect
    if (this.isDelegateClosedOrClosing()) {
      Logger.warn("WebSocket is closed or closing, attempting to reconnect");
      try {
        await this.connect();
      } catch (error) {
        Logger.error("Failed to reconnect WebSocket", error);
        throw error;
      }
    }

    // Send the data using the delegate
    return this.delegate?.sendData(data, timeout);
  }
}
