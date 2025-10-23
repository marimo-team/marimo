/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */

import { WebSocketTransport } from "@open-rpc/client-js";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Mocks } from "@/__mocks__/common";
import { ReconnectingWebSocketTransport } from "../transport";

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

  return {
    WebSocketTransport: mockWebSocketTransport,
  };
});

describe("ReconnectingWebSocketTransport", () => {
  const mockWsUrl = "ws://localhost:8080/lsp";
  let mockConnection: any;

  beforeEach(() => {
    vi.clearAllMocks();

    // Create a mock WebSocket connection with readyState
    mockConnection = {
      readyState: WebSocket.OPEN,
    };

    // Mock the WebSocketTransport constructor to set the connection
    (WebSocketTransport as any).mockImplementation(function (this: any) {
      this.connection = mockConnection;
      this.connect = vi.fn().mockResolvedValue(undefined);
      this.close = vi.fn();
      this.sendData = vi.fn().mockResolvedValue({ result: "success" });
    });
  });

  it("should create a transport with the provided URL function", () => {
    const getWsUrl = vi.fn(() => mockWsUrl);
    const transport = new ReconnectingWebSocketTransport({ getWsUrl });

    expect(transport).toBeDefined();
    expect(getWsUrl).not.toHaveBeenCalled(); // URL function not called until connect
  });

  it("should connect successfully", async () => {
    const getWsUrl = vi.fn(() => mockWsUrl);
    const transport = new ReconnectingWebSocketTransport({ getWsUrl });

    await transport.connect();

    expect(getWsUrl).toHaveBeenCalledTimes(1);
    expect(WebSocketTransport).toHaveBeenCalledWith(mockWsUrl);
  });

  it("should wait for connection before connecting", async () => {
    const getWsUrl = vi.fn(() => mockWsUrl);
    const waitForConnection = vi.fn().mockResolvedValue(undefined);
    const transport = new ReconnectingWebSocketTransport({
      getWsUrl,
      waitForConnection,
    });

    await transport.connect();

    expect(waitForConnection).toHaveBeenCalledTimes(1);
    expect(getWsUrl).toHaveBeenCalledTimes(1);
  });

  it("should reuse the same connection promise if already connecting", async () => {
    const getWsUrl = vi.fn(() => mockWsUrl);
    const waitForConnection = vi
      .fn()
      .mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100)),
      );
    const transport = new ReconnectingWebSocketTransport({
      getWsUrl,
      waitForConnection,
    });

    // Start two connections concurrently
    const promise1 = transport.connect();
    const promise2 = transport.connect();

    await Promise.all([promise1, promise2]);

    // Should only create one delegate
    expect(WebSocketTransport).toHaveBeenCalledTimes(1);
    expect(waitForConnection).toHaveBeenCalledTimes(1);
  });

  it("should send data successfully when connected", async () => {
    const getWsUrl = vi.fn(() => mockWsUrl);
    const transport = new ReconnectingWebSocketTransport({ getWsUrl });

    await transport.connect();

    const data: any = { method: "test", params: [] };
    const result = await transport.sendData(data, 5000);

    expect(result).toEqual({ result: "success" });
  });

  it("should reconnect when WebSocket is in CLOSED state", async () => {
    const getWsUrl = vi.fn(() => mockWsUrl);
    const transport = new ReconnectingWebSocketTransport({ getWsUrl });

    // First connection
    await transport.connect();
    expect(WebSocketTransport).toHaveBeenCalledTimes(1);

    // Simulate WebSocket closing
    mockConnection.readyState = WebSocket.CLOSED;

    // Send data should trigger reconnection
    const data: any = { method: "test", params: [] };
    await transport.sendData(data, 5000);

    // Should have created a new WebSocketTransport
    expect(WebSocketTransport).toHaveBeenCalledTimes(2);
  });

  it("should reconnect when WebSocket is in CLOSING state", async () => {
    const getWsUrl = vi.fn(() => mockWsUrl);
    const transport = new ReconnectingWebSocketTransport({ getWsUrl });

    // First connection
    await transport.connect();
    expect(WebSocketTransport).toHaveBeenCalledTimes(1);

    // Simulate WebSocket closing
    mockConnection.readyState = WebSocket.CLOSING;

    // Send data should trigger reconnection
    const data: any = { method: "test", params: [] };
    await transport.sendData(data, 5000);

    // Should have created a new WebSocketTransport
    expect(WebSocketTransport).toHaveBeenCalledTimes(2);
  });

  it("should close the transport and prevent reconnection", async () => {
    const getWsUrl = vi.fn(() => mockWsUrl);
    const transport = new ReconnectingWebSocketTransport({ getWsUrl });

    await transport.connect();
    transport.close();

    // Attempting to connect again should throw
    await expect(transport.connect()).rejects.toThrow("Transport is closed");
  });

  it("should close old delegate when creating a new one", async () => {
    const getWsUrl = vi.fn(() => mockWsUrl);
    const transport = new ReconnectingWebSocketTransport({ getWsUrl });

    // First connection
    await transport.connect();
    const firstDelegate = (transport as any).delegate;
    expect(firstDelegate).toBeDefined();

    // Simulate connection closed
    mockConnection.readyState = WebSocket.CLOSED;

    // Reconnect by sending data
    const data: any = { method: "test", params: [] };
    await transport.sendData(data, 5000);

    // Old delegate should have been closed
    expect(firstDelegate.close).toHaveBeenCalled();
  });

  it("should handle connection failures gracefully", async () => {
    const getWsUrl = vi.fn(() => mockWsUrl);
    const connectionError = new Error("Connection failed");

    // Mock connect to fail
    (WebSocketTransport as any).mockImplementationOnce(function (this: any) {
      this.connection = mockConnection;
      this.connect = vi.fn().mockRejectedValue(connectionError);
      this.close = vi.fn();
      this.sendData = vi.fn();
    });

    const transport = new ReconnectingWebSocketTransport({ getWsUrl });

    await expect(transport.connect()).rejects.toThrow("Connection failed");

    // Delegate should be cleared after failure
    expect((transport as any).delegate).toBeUndefined();
  });

  it("should handle waitForConnection failures", async () => {
    const getWsUrl = vi.fn(() => mockWsUrl);
    const waitError = new Error("Wait failed");
    const waitForConnection = vi.fn().mockRejectedValue(waitError);

    const transport = new ReconnectingWebSocketTransport({
      getWsUrl,
      waitForConnection,
    });

    await expect(transport.connect()).rejects.toThrow("Wait failed");

    // Should not have created a delegate
    expect(WebSocketTransport).not.toHaveBeenCalled();
  });

  it("should automatically reconnect on sendData after connection loss", async () => {
    const getWsUrl = vi.fn(() => mockWsUrl);
    const transport = new ReconnectingWebSocketTransport({ getWsUrl });

    // Don't connect initially
    // Simulate WebSocket in closed state (no delegate exists)
    expect((transport as any).delegate).toBeUndefined();

    // Send data should trigger automatic connection
    const data: any = { method: "test", params: [] };
    await transport.sendData(data, 5000);

    expect(WebSocketTransport).toHaveBeenCalledTimes(1);
  });
});
