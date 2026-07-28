/* Copyright 2026 Marimo. All rights reserved. */

import { prettyError } from "@/utils/errors";
import { ReconnectingWebSocketTransport } from "@/core/lsp/transport";

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
   * Number of connection attempts in each retry cycle.
   * @default 3
   */
  retries?: number;

  /**
   * Delay between connection attempts in milliseconds.
   * @default 1000
   */
  retryDelayMs?: number;
}

/**
 * Copilot's lazy transport is the shared reconnecting LSP transport with
 * Copilot-specific readiness checks, retries, and user-facing errors.
 */
export class LazyWebsocketTransport extends ReconnectingWebSocketTransport {
  constructor(options: LazyWebsocketTransportOptions) {
    super({
      getWsUrl: options.getWsUrl,
      waitForConnection: options.waitForReady,
      retries: options.retries ?? 3,
      retryDelayMs: options.retryDelayMs ?? 1000,
      onConnectionFailure: (error) => {
        options.showError(
          "GitHub Copilot Connection Error",
          `Failed to connect to GitHub Copilot. Please check your settings and try again.\n\n${prettyError(error)}`,
        );
      },
    });
  }
}
