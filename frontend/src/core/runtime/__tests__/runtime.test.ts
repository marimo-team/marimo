/* Copyright 2024 Marimo. All rights reserved. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SessionId } from "@/core/kernel/session";
import { Logger } from "@/utils/Logger";
import { RuntimeManager } from "../runtime";
import type { RuntimeConfig } from "../types";

// Mock the session module
vi.mock("@/core/kernel/session", () => ({
  getSessionId: () => "test-session-id" as SessionId,
}));

// Mock the Logger module
vi.mock("@/utils/Logger", () => ({
  Logger: {
    error: vi.fn(),
    warn: vi.fn(),
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

  describe("healthURLwithParam", () => {
    it("should return health check URL with param", () => {
      const mockCopy = { ...mockConfig };
      mockCopy.url = "https://example.com/nested?param=value";
      const runtime = new RuntimeManager(mockCopy);
      const url = runtime.healthURL();

      expect(url.protocol).toBe("https:");
      expect(url.pathname).toBe("/nested/health");
      expect(url.searchParams.get("param")).toBe("value");
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
        "Failed to connect after 25 retries",
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
          "x-runtime-url": "https://example.com/",
        }
      `);
    });

    it("should return headers with empty token when not provided", () => {
      const runtime = new RuntimeManager(mockConfigWithoutToken);
      const headers = runtime.headers();

      expect(headers).toEqual({
        "Marimo-Session-Id": "test-session-id",
        "Marimo-Server-Token": "",
        "x-runtime-url": "http://localhost:8080/",
      });
    });
  });

  describe("setDOMBaseUri", () => {
    let originalBase: HTMLBaseElement | null;

    beforeEach(() => {
      // Store and remove existing base element if any
      originalBase = document.querySelector("base");
      if (originalBase) {
        originalBase.remove();
      }
    });

    afterEach(() => {
      // Clean up any base elements created during tests
      const baseElements = document.querySelectorAll("base");
      baseElements.forEach((base) => base.remove());

      // Restore original base element if it existed
      if (originalBase) {
        document.head.append(originalBase);
      }
    });

    it("should not set base URI when health check fails", async () => {
      const runtime = new RuntimeManager(mockConfig);
      // Base element should not be set
      let baseElement = document.querySelector("base");
      expect(baseElement).toBeNull();

      // Mock failed health check
      global.fetch = vi.fn().mockResolvedValue({ ok: false });

      await runtime.isHealthy();

      baseElement = document.querySelector("base");
      expect(baseElement).toBeNull();
    });

    it("should create base element when none exists", async () => {
      const runtime = new RuntimeManager(mockConfig);

      // Mock successful health check
      global.fetch = vi.fn().mockResolvedValue({ ok: true });

      await runtime.isHealthy();

      const baseElement = document.querySelector("base");
      expect(baseElement).toBeTruthy();
      expect(baseElement?.getAttribute("href")).toBe("https://example.com/");
    });

    it("should update existing base element href", async () => {
      // Create existing base element
      const existingBase = document.createElement("base");
      existingBase.setAttribute("href", "https://old-url.com");
      document.head.append(existingBase);

      const runtime = new RuntimeManager(mockConfig);

      // Mock successful health check
      global.fetch = vi.fn().mockResolvedValue({ ok: true });

      await runtime.isHealthy();

      const baseElement = document.querySelector("base");
      expect(baseElement).toBe(existingBase); // Should be the same element
      expect(baseElement?.getAttribute("href")).toBe("https://example.com/");

      // Should only have one base element
      expect(document.querySelectorAll("base")).toHaveLength(1);
    });

    it("should remove query params from base URI", async () => {
      const configWithQueryParams: RuntimeConfig = {
        url: "https://example.com/foo?param1=value1&param2=value2",
        authToken: "test-token",
      };

      const runtime = new RuntimeManager(configWithQueryParams);

      // Mock successful health check
      global.fetch = vi.fn().mockResolvedValue({ ok: true });

      await runtime.isHealthy();

      const baseElement = document.querySelector("base");
      expect(baseElement).toBeTruthy();
      // Query params should be removed from the base href
      expect(baseElement?.getAttribute("href")).toBe(
        "https://example.com/foo/",
      );
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

    it("should preserve all window-level query parameters in URLs", () => {
      // Mock window.location.search with custom query parameters
      const originalLocation = window.location;
      Object.defineProperty(window, "location", {
        value: {
          ...originalLocation,
          search: "?custom_param=value123&user_token=abc&theme=dark",
        },
        writable: true,
      });

      const runtime = new RuntimeManager({
        url: "https://example.com/path?base_param=existing",
      });

      const wsUrl = runtime.getWsURL("test" as SessionId);
      const httpUrl = runtime.formatHttpURL(
        "api/test",
        new URLSearchParams(),
        false,
      );

      // Should preserve base URL query params
      expect(wsUrl.searchParams.get("base_param")).toBe("existing");
      expect(httpUrl.searchParams.get("base_param")).toBe("existing");

      // Should preserve all window-level query params (including custom ones)
      expect(wsUrl.searchParams.get("custom_param")).toBe("value123");
      expect(wsUrl.searchParams.get("user_token")).toBe("abc");
      expect(wsUrl.searchParams.get("theme")).toBe("dark");
      expect(httpUrl.searchParams.get("custom_param")).toBe("value123");
      expect(httpUrl.searchParams.get("user_token")).toBe("abc");
      expect(httpUrl.searchParams.get("theme")).toBe("dark");

      // Should also include session_id for WebSocket URLs
      expect(wsUrl.searchParams.get("session_id")).toBe("test");

      // Restore original location
      Object.defineProperty(window, "location", {
        value: originalLocation,
        writable: true,
      });
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

    it("should handle blob URLs", () => {
      const runtime = new RuntimeManager({
        url: "blob:https://example.com/12345678-1234-1234-1234-123456789abc",
      });

      expect(runtime.httpURL.toString()).toBe(
        "blob:https://example.com/12345678-1234-1234-1234-123456789abc",
      );
    });

    it("should throw when creating WebSocket URLs from blob URLs", () => {
      const runtime = new RuntimeManager({
        url: "blob:https://example.com/12345678-1234-1234-1234-123456789abc",
      });
      const sessionId = "test" as SessionId;

      expect(runtime.getWsURL(sessionId).toString()).toMatchInlineSnapshot(
        `"blob:https://example.com/12345678-1234-1234-1234-123456789abc?session_id=test"`,
      );
      expect(Logger.warn).toHaveBeenCalledOnce();
    });

    it("should handle blob URLs in AI URLs", () => {
      const runtime = new RuntimeManager({
        url: "blob:https://example.com/12345678-1234-1234-1234-123456789abc",
      });
      const aiUrl = runtime.getAiURL("completion");

      expect(aiUrl.protocol).toBe("blob:");
      expect(aiUrl.pathname).toBe(
        "https://example.com/12345678-1234-1234-1234-123456789abc",
      );
    });

    it("should handle blob URLs in health check URLs", () => {
      const runtime = new RuntimeManager({
        url: "blob:https://example.com/12345678-1234-1234-1234-123456789abc",
      });
      const healthUrl = runtime.healthURL();

      expect(healthUrl.protocol).toBe("blob:");
      expect(healthUrl.pathname).toBe(
        "https://example.com/12345678-1234-1234-1234-123456789abc",
      );
    });

    it("should handle URLs with userinfo", () => {
      const runtime = new RuntimeManager({
        url: "https://user:pass@example.com",
      });
      const wsUrl = runtime.getWsURL("test" as SessionId);

      expect(wsUrl.protocol).toBe("wss:");
      expect(wsUrl.username).toBe("user");
      expect(wsUrl.password).toBe("pass");
      expect(wsUrl.hostname).toBe("example.com");
    });

    it("should handle IPv6 addresses", () => {
      const runtime = new RuntimeManager({
        url: "http://[::1]:8080",
      });
      const wsUrl = runtime.getWsURL("test" as SessionId);

      expect(wsUrl.protocol).toBe("ws:");
      expect(wsUrl.hostname).toBe("[::1]");
      expect(wsUrl.port).toBe("8080");
    });

    it("should handle URLs with encoded characters", () => {
      const runtime = new RuntimeManager({
        url: "https://example.com/path%20with%20spaces",
      });
      const aiUrl = runtime.getAiURL("completion");

      expect(aiUrl.pathname).toBe("/path%20with%20spaces/api/ai/completion");
    });

    it("should handle URLs with multiple trailing slashes", () => {
      const runtime = new RuntimeManager({
        url: "https://example.com/path///",
      });
      const aiUrl = runtime.getAiURL("completion");

      expect(aiUrl.pathname).toBe("/path///api/ai/completion");
    });

    it("should handle URLs with port numbers", () => {
      const runtime = new RuntimeManager({
        url: "https://example.com:9443/app",
      });
      const wsUrl = runtime.getWsURL("test" as SessionId);

      expect(wsUrl.protocol).toBe("wss:");
      expect(wsUrl.hostname).toBe("example.com");
      expect(wsUrl.port).toBe("9443");
      expect(wsUrl.pathname).toBe("/app/ws");
    });

    it("should handle localhost variations", () => {
      const variants = [
        "http://127.0.0.1:8080",
        "http://localhost:8080",
        "http://[::1]:8080",
      ];

      variants.forEach((url) => {
        const runtime = new RuntimeManager({ url });
        const wsUrl = runtime.getWsURL("test" as SessionId);
        expect(wsUrl.protocol).toBe("ws:");
      });
    });

    it("should handle URLs with complex query parameters", () => {
      const runtime = new RuntimeManager({
        url: "https://example.com?param1=value1&param2=value%20encoded&empty=",
      });
      const wsUrl = runtime.getWsURL("test" as SessionId);

      expect(wsUrl.searchParams.get("param1")).toBe("value1");
      expect(wsUrl.searchParams.get("param2")).toBe("value encoded");
      expect(wsUrl.searchParams.get("empty")).toBe("");
      expect(wsUrl.searchParams.get("session_id")).toBe("test");
    });

    it("should accept data URLs (valid URL format)", () => {
      const runtime = new RuntimeManager({
        url: "data:text/plain;base64,SGVsbG8gV29ybGQ=",
      });
      expect(runtime.httpURL.protocol).toBe("data:");
    });

    it("should accept file URLs (valid URL format)", () => {
      const runtime = new RuntimeManager({ url: "file:///path/to/file" });
      expect(runtime.httpURL.protocol).toBe("file:");
    });

    it("should accept custom protocol URLs (valid URL format)", () => {
      const runtime = new RuntimeManager({ url: "custom://example.com" });
      expect(runtime.httpURL.protocol).toBe("custom:");
    });

    it("should handle empty string URL", () => {
      expect(() => {
        new RuntimeManager({ url: "" });
      }).toThrow("Invalid runtime URL");
    });

    it("should handle malformed URLs", () => {
      const malformedUrls = [
        "http://",
        "https://",
        "not-a-url",
        "http://[invalid-ipv6",
        "https://exam ple.com", // space in hostname
      ];

      malformedUrls.forEach((url) => {
        expect(() => {
          new RuntimeManager({ url });
        }).toThrow("Invalid runtime URL");
      });
    });
  });
});
