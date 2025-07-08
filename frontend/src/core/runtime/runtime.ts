/* Copyright 2024 Marimo. All rights reserved. */

import { Deferred } from "@/utils/Deferred";
import { Logger } from "@/utils/Logger";
import { KnownQueryParams } from "../constants";
import { isIslands } from "../islands/utils";
import { getSessionId, type SessionId } from "../kernel/session";
import { isWasm } from "../wasm/utils";
import type { RuntimeConfig } from "./types";

export class RuntimeManager {
  private initialHealthyCheck = new Deferred<void>();

  constructor(
    private config: RuntimeConfig,
    private lazy = false,
  ) {
    // Validate the URL on construction
    try {
      new URL(this.config.url);
    } catch (error) {
      throw new Error(
        `Invalid runtime URL: ${this.config.url}. ${error instanceof Error ? error.message : "Unknown error"}`,
      );
    }

    if (!this.lazy) {
      this.init();
    }
  }

  get httpURL(): URL {
    return new URL(this.config.url);
  }

  get isSameOrigin(): boolean {
    return this.httpURL.origin === window.location.origin;
  }

  /**
   * The base URL of the runtime.
   */
  formatHttpURL(
    path?: string,
    searchParams?: URLSearchParams,
    restrictToKnownQueryParams = true,
  ): URL {
    if (!path) {
      path = "";
    }
    // URL may be something like "http://localhost:8000?auth=123"
    const baseUrl = this.httpURL;
    const currentParams = new URLSearchParams(window.location.search);
    // Copy over search params if provided
    if (searchParams) {
      for (const [key, value] of searchParams.entries()) {
        baseUrl.searchParams.set(key, value);
      }
    }

    for (const [key, value] of currentParams.entries()) {
      if (
        restrictToKnownQueryParams &&
        !Object.values(KnownQueryParams).includes(key)
      ) {
        continue;
      }
      baseUrl.searchParams.set(key, value);
    }

    const cleanPath = baseUrl.pathname.replace(/\/$/, "");
    baseUrl.pathname = `${cleanPath}/${path.replace(/^\//, "")}`;
    baseUrl.hash = "";
    return baseUrl;
  }

  formatWsURL(path: string, searchParams?: URLSearchParams): URL {
    // We don't restrict to known query parameters, since mo.query_params()
    // can accept arbitrary parameters.
    const url = this.formatHttpURL(
      path,
      searchParams,
      /* restrictToKnownQueryParams =*/ false,
    );
    return asWsUrl(url.toString());
  }

  /**
   * The WebSocket URL of the runtime.
   */
  getWsURL(sessionId: SessionId): URL {
    const baseUrl = new URL(this.config.url);
    const searchParams = new URLSearchParams(baseUrl.search);

    // Merge in current page's query parameters
    const currentParams = new URLSearchParams(window.location.search);
    currentParams.forEach((value, key) => {
      // Don't override base URL params
      if (!searchParams.has(key)) {
        searchParams.set(key, value);
      }
    });

    searchParams.set(KnownQueryParams.sessionId, sessionId);
    return this.formatWsURL("/ws", searchParams);
  }

  /**
   * The WebSocket Sync URL of the runtime, for real-time updates.
   */
  getWsSyncURL(sessionId: SessionId): URL {
    const baseUrl = new URL(this.config.url);
    const searchParams = new URLSearchParams(baseUrl.search);

    // Merge in current page's query parameters
    const currentParams = new URLSearchParams(window.location.search);
    currentParams.forEach((value, key) => {
      // Don't override base URL params
      if (!searchParams.has(key)) {
        searchParams.set(key, value);
      }
    });

    searchParams.set(KnownQueryParams.sessionId, sessionId);
    return this.formatWsURL("/ws_sync", searchParams);
  }

  /**
   * The WebSocket URL of the terminal.
   */
  getTerminalWsURL(): URL {
    return this.formatWsURL("/terminal/ws");
  }

  /**
   * The URL of the copilot server.
   */
  getLSPURL(lsp: "pylsp" | "copilot"): URL {
    if (lsp === "copilot") {
      // For copilot, don't include any query parameters
      const url = this.formatWsURL(`/lsp/${lsp}`);
      url.search = "";
      return url;
    }
    return this.formatWsURL(`/lsp/${lsp}`);
  }

  getAiURL(path: "completion" | "chat"): URL {
    return this.formatHttpURL(`/api/ai/${path}`);
  }

  /**
   * The URL of the health check endpoint.
   */
  healthURL(): URL {
    return this.formatHttpURL("/health");
  }

  async isHealthy(): Promise<boolean> {
    // Always healthy if WASM
    if (isWasm() || isIslands()) {
      return true;
    }

    try {
      const response = await fetch(this.healthURL().toString());
      // If there is a redirect, update the URL in the config
      if (response.redirected) {
        // strip /health from the URL
        this.config.url = response.url.replace(/\/health$/, "");
      }
      return response.ok;
    } catch {
      return false;
    }
  }

  async init(options?: { disableRetryDelay?: boolean }) {
    let retries = 0;
    // This matches backoff logic elsewhere.
    const maxRetries = 25;
    const baseDelay = 100; // 0.1 second
    const growthFactor = 1.2;
    const maxDelay = 2000;

    while (!(await this.isHealthy())) {
      if (retries >= maxRetries) {
        Logger.error(`Failed to connect after ${maxRetries} retries`);
        this.initialHealthyCheck.reject(
          new Error(`Failed to connect after ${maxRetries} retries`),
        );
        return;
      }
      if (!options?.disableRetryDelay) {
        const delay = Math.min(baseDelay * growthFactor ** retries, maxDelay);
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
      retries++;
    }

    this.initialHealthyCheck.resolve();
  }

  /**
   * Wait for the runtime to be healthy.
   */
  async waitForHealthy(): Promise<void> {
    return this.initialHealthyCheck.promise;
  }

  headers(): Record<string, string> {
    const headers: Record<string, string> = {
      "Marimo-Session-Id": getSessionId(),
      "Marimo-Server-Token": this.config.serverToken ?? "",
    };

    if (this.config.authToken) {
      headers.Authorization = `Bearer ${this.config.authToken}`;
    }

    return headers;
  }
}

function asWsUrl(url: string): URL {
  if (!url.startsWith("http")) {
    Logger.warn(`URL must start with http: ${url}`);
    const newUrl = new URL(url);
    newUrl.protocol = "ws";
    return newUrl;
  }
  // Replace the protocol http with ws
  return new URL(url.replace(/^http/, "ws"));
}
