/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it, vi } from "vitest";
import { RuntimeManager } from "../runtime";
import type { RuntimeConfig } from "../types";
import type { SessionId } from "@/core/kernel/session";

// Mock the session module
vi.mock("@/core/kernel/session", () => ({
  getSessionId: () => "test-session-id" as SessionId,
}));

// Mock the Logger module
vi.mock("@/utils/Logger", () => ({
  Logger: {
    error: vi.fn(),
  },
}));

describe("RuntimeManager", () => {
  const mockConfig: RuntimeConfig = {
    url: "https://example.com",
    authToken: "test-token",
  };

  const mockConfigWithoutToken: RuntimeConfig = {
    url: "http://localhost:8080",
  };

  describe("constructor", () => {
    it("should create instance with config", () => {
      const runtime = new RuntimeManager(mockConfig);
      expect(runtime).toBeInstanceOf(RuntimeManager);
    });
  });

  describe("httpURL", () => {
    it("should return base URL as URL object", () => {
      const runtime = new RuntimeManager(mockConfig);
      const url = runtime.httpURL;
      expect(url).toBeInstanceOf(URL);
      expect(url.toString()).toBe("https://example.com/");
    });

    it("should handle URLs without trailing slash", () => {
      const runtime = new RuntimeManager({ url: "https://example.com/path" });
      expect(runtime.httpURL.toString()).toBe("https://example.com/path");
    });
  });

  describe("getWsURL", () => {
    it("should return WebSocket URL with session ID for https", () => {
      const runtime = new RuntimeManager(mockConfig);
      const sessionId = "1234" as SessionId;
      const url = runtime.getWsURL(sessionId);

      expect(url.protocol).toBe("wss:");
      expect(url.hostname).toBe("example.com");
      expect(url.pathname).toBe("/ws");
      expect(url.searchParams.get("session_id")).toBe(sessionId);
    });

    it("should return WebSocket URL for http", () => {
      const runtime = new RuntimeManager(mockConfigWithoutToken);
      const sessionId = "1234" as SessionId;
      const url = runtime.getWsURL(sessionId);

      expect(url.protocol).toBe("ws:");
      expect(url.hostname).toBe("localhost");
      expect(url.port).toBe("8080");
      expect(url.searchParams.get("session_id")).toBe(sessionId);
    });

    it("should preserve existing query params", () => {
      const runtime = new RuntimeManager({ url: "http://example.com?foo=bar" });
      const sessionId = "1234" as SessionId;
      const url = runtime.getWsURL(sessionId);

      expect(url.searchParams.get("foo")).toBe("bar");
      expect(url.searchParams.get("session_id")).toBe(sessionId);
    });
  });

  describe("getWsSyncURL", () => {
    it("should return WebSocket Sync URL", () => {
      const runtime = new RuntimeManager(mockConfig);
      const sessionId = "1234" as SessionId;
      const url = runtime.getWsSyncURL(sessionId);

      expect(url.protocol).toBe("wss:");
      expect(url.pathname).toBe("/ws_sync");
      expect(url.searchParams.get("session_id")).toBe(sessionId);
    });
  });

  describe("getTerminalWsURL", () => {
    it("should return terminal WebSocket URL", () => {
      const runtime = new RuntimeManager(mockConfig);
      const url = runtime.getTerminalWsURL();

      expect(url.protocol).toBe("wss:");
      expect(url.pathname).toBe("/terminal/ws");
    });
  });

  describe("getLSPURL", () => {
    it("should return pylsp URL", () => {
      const runtime = new RuntimeManager(mockConfig);
      const url = runtime.getLSPURL("pylsp");

      expect(url.protocol).toBe("wss:");
      expect(url.pathname).toBe("/lsp/pylsp");
    });

    it("should return copilot URL", () => {
      const runtime = new RuntimeManager(mockConfig);
      const url = runtime.getLSPURL("copilot");

      expect(url.protocol).toBe("wss:");
      expect(url.pathname).toBe("/lsp/copilot");
    });
  });

  describe("getAiURL", () => {
    it("should return AI completion URL", () => {
      const runtime = new RuntimeManager(mockConfig);
      const url = runtime.getAiURL("completion");

      expect(url.protocol).toBe("https:");
      expect(url.pathname).toBe("/api/ai/completion");
    });

    it("should return AI chat URL", () => {
      const runtime = new RuntimeManager(mockConfig);
      const url = runtime.getAiURL("chat");

      expect(url.protocol).toBe("https:");
      expect(url.pathname).toBe("/api/ai/chat");
    });
  });

  describe("healthURL", () => {
    it("should return health check URL", () => {
      const runtime = new RuntimeManager(mockConfig);
      const url = runtime.healthURL();

      expect(url.protocol).toBe("https:");
      expect(url.pathname).toBe("/health");
    });
  });

  describe("isHealthy", () => {
    it("should return true for successful health check", async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
      });

      const runtime = new RuntimeManager(mockConfig);
      const result = await runtime.isHealthy();

      expect(result).toBe(true);
      expect(fetch).toHaveBeenCalledWith("https://example.com/health");
    });

    it("should return false for failed health check", async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
      });

      const runtime = new RuntimeManager(mockConfig);
      const result = await runtime.isHealthy();

      expect(result).toBe(false);
    });

    it("should return false and log error when fetch throws", async () => {
      const error = new Error("Network error");
      global.fetch = vi.fn().mockRejectedValue(error);

      const runtime = new RuntimeManager(mockConfig);
      const result = await runtime.isHealthy();

      expect(result).toBe(false);
    });
  });

  describe("waitForHealthy", () => {
    it("should resolve immediately if healthy", async () => {
      const runtime = new RuntimeManager(mockConfig, true);

      vi.spyOn(runtime, "isHealthy").mockResolvedValue(true);
      runtime.init();

      await expect(runtime.waitForHealthy()).resolves.toBeUndefined();
    });

    it("should retry and eventually succeed", async () => {
      const runtime = new RuntimeManager(mockConfig, true);
      const healthySpy = vi
        .spyOn(runtime, "isHealthy")
        .mockResolvedValueOnce(false)
        .mockResolvedValueOnce(false)
        .mockResolvedValueOnce(true);

      runtime.init({ disableRetryDelay: true });

      await expect(runtime.waitForHealthy()).resolves.toBeUndefined();
      expect(healthySpy).toHaveBeenCalledTimes(3);
    });

    it("should throw after max retries", async () => {
      const runtime = new RuntimeManager(mockConfig, true);
      vi.spyOn(runtime, "isHealthy").mockResolvedValue(false);
      runtime.init({ disableRetryDelay: true });

      await expect(runtime.waitForHealthy()).rejects.toThrow(
        "Failed to connect after 6 retries",
      );
    });
  });

  describe("headers", () => {
    it("should return headers with auth token", () => {
      const runtime = new RuntimeManager(mockConfig);
      const headers = runtime.headers();

      expect(headers).toMatchInlineSnapshot(`
        {
          "Authorization": "Bearer test-token",
          "Marimo-Server-Token": "",
          "Marimo-Session-Id": "test-session-id",
        }
      `);
    });

    it("should return headers with empty token when not provided", () => {
      const runtime = new RuntimeManager(mockConfigWithoutToken);
      const headers = runtime.headers();

      expect(headers).toEqual({
        "Marimo-Session-Id": "test-session-id",
        "Marimo-Server-Token": "",
      });
    });
  });

  describe("edge cases", () => {
    it("should handle URLs with nested paths", () => {
      const runtime = new RuntimeManager({
        url: "https://example.com/nested/path/",
      });
      const wsUrl = runtime.getWsURL("test" as SessionId);
      const aiUrl = runtime.getAiURL("completion");

      expect(wsUrl.pathname).toBe("/nested/path/ws");
      expect(aiUrl.pathname).toBe("/nested/path/api/ai/completion");
    });

    it("should handle URLs with query parameters and fragments", () => {
      const runtime = new RuntimeManager({
        url: "https://example.com/path?existing=param#fragment",
      });
      const wsUrl = runtime.getWsURL("test" as SessionId);

      expect(wsUrl.searchParams.get("existing")).toBe("param");
      expect(wsUrl.searchParams.get("session_id")).toBe("test");
      // Fragment should not be preserved in WebSocket URLs
      expect(wsUrl.hash).toBe("");
    });

    it("should throw for invalid URLs", () => {
      expect(() => {
        new RuntimeManager({ url: "not-a-url" });
      }).toThrow();
    });

    it("should handle http to ws conversion correctly", () => {
      const httpRuntime = new RuntimeManager({ url: "http://localhost" });
      const httpsRuntime = new RuntimeManager({ url: "https://localhost" });

      expect(httpRuntime.getWsURL("test" as SessionId).protocol).toBe("ws:");
      expect(httpsRuntime.getWsURL("test" as SessionId).protocol).toBe("wss:");
    });
  });
});
