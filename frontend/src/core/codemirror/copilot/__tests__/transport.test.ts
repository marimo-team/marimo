/* Copyright 2026 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */

import { WebSocketTransport } from "@open-rpc/client-js";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Mocks } from "@/__mocks__/common";
import { LazyWebsocketTransport } from "../transport";

// Mock the Logger
vi.mock("@/utils/Logger", () => ({
  Logger: Mocks.logger(),
}));

// Mock the WebSocketTransport
vi.mock("@open-rpc/client-js", () => {
  const mockWebSocketTransport = vi.fn();
  mockWebSocketTransport.prototype.connect = vi.fn();
  mockWebSocketTransport.prototype.close = vi.fn();
  mockWebSocketTransport.prototype.sendData = vi.fn();
  mockWebSocketTransport.prototype.subscribe = vi.fn();
  mockWebSocketTransport.prototype.unsubscribe = vi.fn();

  return {
    WebSocketTransport: mockWebSocketTransport,
  };
});

describe("LazyWebsocketTransport", () => {
  const mockWsUrl = "ws://localhost:8080/copilot";
  let mockGetWsUrl: ReturnType<typeof vi.fn>;
  let mockWaitForReady: ReturnType<typeof vi.fn>;
  let mockShowError: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();

    mockGetWsUrl = vi.fn(() => mockWsUrl);
    mockWaitForReady = vi.fn().mockResolvedValue(undefined);
    mockShowError = vi.fn();

    // Mock the WebSocketTransport constructor
    (WebSocketTransport as any).mockImplementation(function (this: any) {
      this.connect = vi.fn().mockResolvedValue(undefined);
      this.close = vi.fn();
      this.sendData = vi.fn().mockResolvedValue({ result: "success" });
      this.subscribe = vi.fn();
      this.unsubscribe = vi.fn();
    });
  });

  describe("constructor", () => {
    it("should create a transport with default options", () => {
      const transport = new LazyWebsocketTransport({
        getWsUrl: mockGetWsUrl,
        waitForReady: mockWaitForReady,
        showError: mockShowError,
      });

      expect(transport).toBeDefined();
      expect(mockGetWsUrl).not.toHaveBeenCalled();
    });

    it("should accept custom retry options", () => {
      const transport = new LazyWebsocketTransport({
        getWsUrl: mockGetWsUrl,
        waitForReady: mockWaitForReady,
        showError: mockShowError,
        retries: 5,
        retryDelayMs: 2000,
        maxTimeoutMs: 10_000,
      });

      expect(transport).toBeDefined();
    });
  });

  describe("connect", () => {
    it("should wait for prerequisites before connecting", async () => {
      const transport = new LazyWebsocketTransport({
        getWsUrl: mockGetWsUrl,
        waitForReady: mockWaitForReady,
        showError: mockShowError,
      });

      await transport.connect();

      expect(mockWaitForReady).toHaveBeenCalledTimes(1);
      expect(mockGetWsUrl).toHaveBeenCalledTimes(1);
      expect(WebSocketTransport).toHaveBeenCalledWith(mockWsUrl);
    });

    it("should create delegate and connect", async () => {
      const transport = new LazyWebsocketTransport({
        getWsUrl: mockGetWsUrl,
        waitForReady: mockWaitForReady,
        showError: mockShowError,
      });

      await transport.connect();

      const delegate = (transport as any).delegate;
      expect(delegate).toBeDefined();
      expect(delegate.connect).toHaveBeenCalledTimes(1);
    });

    it("should retry on connection failure", async () => {
      let attemptCount = 0;
      (WebSocketTransport as any).mockImplementation(function (this: any) {
        this.connect = vi.fn().mockImplementation(() => {
          attemptCount++;
          if (attemptCount < 2) {
            return Promise.reject(new Error("Connection failed"));
          }
          return Promise.resolve(undefined);
        });
        this.close = vi.fn();
        this.sendData = vi.fn();
        this.subscribe = vi.fn();
        this.unsubscribe = vi.fn();
      });

      const transport = new LazyWebsocketTransport({
        getWsUrl: mockGetWsUrl,
        waitForReady: mockWaitForReady,
        showError: mockShowError,
        retries: 3,
        retryDelayMs: 10,
      });

      await transport.connect();

      expect(attemptCount).toBe(2);
    });

    it("should show error toast on final retry failure", async () => {
      const connectionError = new Error("Connection failed");
      (WebSocketTransport as any).mockImplementation(function (this: any) {
        this.connect = vi.fn().mockRejectedValue(connectionError);
        this.close = vi.fn();
        this.sendData = vi.fn();
        this.subscribe = vi.fn();
        this.unsubscribe = vi.fn();
      });

      const transport = new LazyWebsocketTransport({
        getWsUrl: mockGetWsUrl,
        waitForReady: mockWaitForReady,
        showError: mockShowError,
        retries: 2,
        retryDelayMs: 10,
      });

      await expect(transport.connect()).rejects.toThrow("Connection failed");

      expect(mockShowError).toHaveBeenCalledTimes(1);
      expect(mockShowError).toHaveBeenCalledWith(
        "GitHub Copilot Connection Error",
        "Failed to connect to GitHub Copilot. Please check your settings and try again.\n\nConnection failed",
      );
      expect((transport as any).delegate).toBeUndefined();
    });

    it("should handle waitForReady failure", async () => {
      const waitError = new Error("Prerequisites not ready");
      mockWaitForReady.mockRejectedValue(waitError);

      const transport = new LazyWebsocketTransport({
        getWsUrl: mockGetWsUrl,
        waitForReady: mockWaitForReady,
        showError: mockShowError,
      });

      await expect(transport.connect()).rejects.toThrow(
        "Prerequisites not ready",
      );
      expect(WebSocketTransport).not.toHaveBeenCalled();
    });
  });

  describe("subscribe", () => {
    it("should register handler on parent and track subscription", () => {
      const transport = new LazyWebsocketTransport({
        getWsUrl: mockGetWsUrl,
        waitForReady: mockWaitForReady,
        showError: mockShowError,
      });

      const handler = vi.fn();
      transport.subscribe("notification", handler);

      expect((transport as any).pendingSubscriptions).toHaveLength(1);
      expect((transport as any).pendingSubscriptions[0]).toEqual({
        event: "notification",
        handler,
      });
    });

    it("should register handler on delegate if it exists", async () => {
      const transport = new LazyWebsocketTransport({
        getWsUrl: mockGetWsUrl,
        waitForReady: mockWaitForReady,
        showError: mockShowError,
      });

      await transport.connect();

      const handler = vi.fn();
      transport.subscribe("notification", handler);

      const delegate = (transport as any).delegate;
      expect(delegate.subscribe).toHaveBeenCalledWith("notification", handler);
    });

    it("should register pending subscriptions when delegate is created", async () => {
      const transport = new LazyWebsocketTransport({
        getWsUrl: mockGetWsUrl,
        waitForReady: mockWaitForReady,
        showError: mockShowError,
      });

      const handler1 = vi.fn();
      const handler2 = vi.fn();
      transport.subscribe("notification", handler1);
      transport.subscribe("response", handler2);

      await transport.connect();

      const delegate = (transport as any).delegate;
      expect(delegate.subscribe).toHaveBeenCalledWith("notification", handler1);
      expect(delegate.subscribe).toHaveBeenCalledWith("response", handler2);
    });
  });

  describe("unsubscribe", () => {
    it("should remove specific handler for specific event", () => {
      const transport = new LazyWebsocketTransport({
        getWsUrl: mockGetWsUrl,
        waitForReady: mockWaitForReady,
        showError: mockShowError,
      });

      const handler1 = vi.fn();
      const handler2 = vi.fn();
      transport.subscribe("notification", handler1);
      transport.subscribe("notification", handler2);

      expect((transport as any).pendingSubscriptions).toHaveLength(2);

      transport.unsubscribe("notification", handler1);

      expect((transport as any).pendingSubscriptions).toHaveLength(1);
      expect((transport as any).pendingSubscriptions[0].handler).toBe(handler2);
    });

    it("should remove handler from all events when event not specified", () => {
      const transport = new LazyWebsocketTransport({
        getWsUrl: mockGetWsUrl,
        waitForReady: mockWaitForReady,
        showError: mockShowError,
      });

      const handler = vi.fn();
      transport.subscribe("notification", handler);
      transport.subscribe("response", handler);

      expect((transport as any).pendingSubscriptions).toHaveLength(2);

      transport.unsubscribe(undefined, handler);

      expect((transport as any).pendingSubscriptions).toHaveLength(0);
    });

    it("should remove all handlers for event when handler not specified", () => {
      const transport = new LazyWebsocketTransport({
        getWsUrl: mockGetWsUrl,
        waitForReady: mockWaitForReady,
        showError: mockShowError,
      });

      const handler1 = vi.fn();
      const handler2 = vi.fn();
      transport.subscribe("notification", handler1);
      transport.subscribe("notification", handler2);
      transport.subscribe("response", handler1);

      expect((transport as any).pendingSubscriptions).toHaveLength(3);

      transport.unsubscribe("notification");

      expect((transport as any).pendingSubscriptions).toHaveLength(1);
      expect((transport as any).pendingSubscriptions[0].event).toBe("response");
    });

    it("should remove all subscriptions when neither event nor handler specified", () => {
      const transport = new LazyWebsocketTransport({
        getWsUrl: mockGetWsUrl,
        waitForReady: mockWaitForReady,
        showError: mockShowError,
      });

      transport.subscribe("notification", vi.fn());
      transport.subscribe("response", vi.fn());

      expect((transport as any).pendingSubscriptions).toHaveLength(2);

      transport.unsubscribe();

      expect((transport as any).pendingSubscriptions).toHaveLength(0);
    });

    it("should unsubscribe from delegate if it exists", async () => {
      const transport = new LazyWebsocketTransport({
        getWsUrl: mockGetWsUrl,
        waitForReady: mockWaitForReady,
        showError: mockShowError,
      });

      await transport.connect();

      const handler = vi.fn();
      transport.subscribe("notification", handler);
      transport.unsubscribe("notification", handler);

      const delegate = (transport as any).delegate;
      expect(delegate.unsubscribe).toHaveBeenCalledWith(
        "notification",
        handler,
      );
    });
  });

  describe("sendData", () => {
    it("should send data through delegate when connected", async () => {
      const transport = new LazyWebsocketTransport({
        getWsUrl: mockGetWsUrl,
        waitForReady: mockWaitForReady,
        showError: mockShowError,
      });

      await transport.connect();

      const data: any = { method: "test", params: [] };
      const result = await transport.sendData(data, 5000);

      const delegate = (transport as any).delegate;
      expect(delegate.sendData).toHaveBeenCalledWith(data, 5000);
      expect(result).toEqual({ result: "success" });
    });

    it("should reconnect if delegate is undefined", async () => {
      const transport = new LazyWebsocketTransport({
        getWsUrl: mockGetWsUrl,
        waitForReady: mockWaitForReady,
        showError: mockShowError,
      });

      const data: any = { method: "test", params: [] };
      await transport.sendData(data, 5000);

      // sendData calls tryConnect directly, not connect, so wait functions aren't called
      // But it should still create and connect the delegate
      expect(WebSocketTransport).toHaveBeenCalled();
      const delegate = (transport as any).delegate;
      expect(delegate).toBeDefined();
      expect(delegate.connect).toHaveBeenCalled();
    });

    it("should clamp timeout to maxTimeoutMs", async () => {
      const transport = new LazyWebsocketTransport({
        getWsUrl: mockGetWsUrl,
        waitForReady: mockWaitForReady,
        showError: mockShowError,
        maxTimeoutMs: 5000,
      });

      await transport.connect();

      const data: any = { method: "test", params: [] };
      await transport.sendData(data, 10_000);

      const delegate = (transport as any).delegate;
      expect(delegate.sendData).toHaveBeenCalledWith(data, 5000);
    });

    it("should throw error if reconnection fails", async () => {
      const connectionError = new Error("Connection failed");
      (WebSocketTransport as any).mockImplementation(function (this: any) {
        this.connect = vi.fn().mockRejectedValue(connectionError);
        this.close = vi.fn();
        this.sendData = vi.fn();
        this.subscribe = vi.fn();
        this.unsubscribe = vi.fn();
      });

      const transport = new LazyWebsocketTransport({
        getWsUrl: mockGetWsUrl,
        waitForReady: mockWaitForReady,
        showError: mockShowError,
        retries: 1,
        retryDelayMs: 10,
      });

      const data: any = { method: "test", params: [] };
      await expect(transport.sendData(data, 5000)).rejects.toThrow(
        "Unable to connect to GitHub Copilot",
      );
    });
  });

  describe("close", () => {
    it("should close delegate and clear it", async () => {
      const transport = new LazyWebsocketTransport({
        getWsUrl: mockGetWsUrl,
        waitForReady: mockWaitForReady,
        showError: mockShowError,
      });

      await transport.connect();

      const delegate = (transport as any).delegate;
      expect(delegate).toBeDefined();

      transport.close();

      expect(delegate.close).toHaveBeenCalledTimes(1);
      expect((transport as any).delegate).toBeUndefined();
    });

    it("should handle close when delegate is undefined", () => {
      const transport = new LazyWebsocketTransport({
        getWsUrl: mockGetWsUrl,
        waitForReady: mockWaitForReady,
        showError: mockShowError,
      });

      expect(() => transport.close()).not.toThrow();
    });
  });
});
