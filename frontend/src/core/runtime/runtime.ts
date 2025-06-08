/* Copyright 2024 Marimo. All rights reserved. */
import { invariant } from "@/utils/invariant";
import type { RuntimeConfig } from "./types";
import { urlJoin } from "./utils";
import { Logger } from "@/utils/Logger";
import { getSessionId, type SessionId } from "../kernel/session";
import { KnownQueryParams } from "../constants";

export class RuntimeManager {
  constructor(private config: RuntimeConfig) {
    // Validate the URL on construction
    try {
      new URL(this.config.url);
    } catch (error) {
      throw new Error(
        `Invalid runtime URL: ${this.config.url}. ${error instanceof Error ? error.message : "Unknown error"}`,
      );
    }
  }

  /**
   * The base URL of the runtime.
   */
  get httpURL(): URL {
    return new URL(this.config.url);
  }

  /**
   * The WebSocket URL of the runtime.
   */
  getWsURL(sessionId: SessionId): URL {
    const wsUrl = asWsUrl(this.config.url);
    const baseUrl = new URL(wsUrl);
    const searchParams = new URLSearchParams(baseUrl.search);
    const currentParams = new URLSearchParams(window.location.search);

    searchParams.set(KnownQueryParams.sessionId, sessionId);

    // Move over window level parameters to the WebSocket URL
    // if they are "known" query params.
    for (const lookup in KnownQueryParams) {
      const key = KnownQueryParams[lookup as keyof typeof KnownQueryParams];
      if (currentParams.has(key)) {
        searchParams.set(key, currentParams.get(key));
      }
    }
    return new URL(
      urlJoin(wsUrl.split("?")[0], `ws?${searchParams.toString()}`),
    );
  }

  /**
   * The WebSocket Sync URL of the runtime, for real-time updates.
   */
  getWsSyncURL(sessionId: SessionId): URL {
    const wsSyncUrl = asWsUrl(this.config.url);
    const baseUrl = new URL(wsSyncUrl);
    const searchParams = new URLSearchParams(baseUrl.search);
    searchParams.set(KnownQueryParams.sessionId, sessionId);
    return new URL(
      urlJoin(wsSyncUrl.split("?")[0], `ws_sync?${searchParams.toString()}`),
    );
  }

  /**
   * The WebSocket URL of the terminal.
   */
  getTerminalWsURL(): URL {
    const terminalUrl = asWsUrl(this.config.url);
    return new URL(urlJoin(terminalUrl, "terminal/ws"));
  }

  /**
   * The URL of the copilot server.
   */
  getLSPURL(lsp: "pylsp" | "copilot"): URL {
    const lspUrl = asWsUrl(this.config.url);
    return new URL(urlJoin(lspUrl, `lsp/${lsp}`));
  }

  getAiURL(path: "completion" | "chat"): URL {
    return new URL(urlJoin(this.httpURL.toString(), `api/ai/${path}`));
  }

  /**
   * The URL of the health check endpoint.
   */
  healthURL(): URL {
    return new URL(urlJoin(this.httpURL.toString(), "health"));
  }

  async isHealthy(): Promise<boolean> {
    try {
      const response = await fetch(this.healthURL().toString());
      return response.ok;
    } catch (error) {
      Logger.error("Failed to check health", error);
      return false;
    }
  }

  /**
   * Wait for the runtime to be healthy.
   * @throws if the runtime is not healthy after 5 retries
   */
  async waitForHealthy(): Promise<void> {
    let retries = 0;
    const maxRetries = 5;
    const baseDelay = 1000;

    while (!(await this.isHealthy())) {
      if (retries >= maxRetries) {
        throw new Error("Failed to connect after 5 retries");
      }
      const delay = baseDelay * 2 ** retries;
      await new Promise((resolve) => setTimeout(resolve, delay));
      retries++;
    }
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

function asWsUrl(url: string): string {
  invariant(url.startsWith("http"), "URL must start with http");
  // Replace the protocol http with ws
  return url.replace(/^http/, "ws");
}
