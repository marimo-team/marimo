/* Copyright 2026 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */

import { Transport } from "@open-rpc/client-js/build/transports/Transport";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CopilotLanguageServerClient } from "../language-server";

// Mock transport
class MockTransport extends Transport {
  override connect = vi.fn().mockResolvedValue(undefined);
  override close = vi.fn();
  override sendData = vi.fn().mockResolvedValue({});
  override subscribe = vi.fn();
  override unsubscribe = vi.fn();
  override parseData = vi.fn();
}

describe("CopilotLanguageServerClient", () => {
  let mockTransport: MockTransport;

  beforeEach(() => {
    mockTransport = new MockTransport();
  });

  it("should initialize without copilot settings", () => {
    const client = new CopilotLanguageServerClient({
      rootUri: "file:///test",
      workspaceFolders: null,
      transport: mockTransport,
    });

    expect(client).toBeDefined();
  });

  it("should initialize with empty copilot settings", () => {
    const client = new CopilotLanguageServerClient({
      rootUri: "file:///test",
      workspaceFolders: null,
      transport: mockTransport,
      copilotSettings: {},
    });

    expect(client).toBeDefined();
  });

  it("should initialize with copilot settings", () => {
    const copilotSettings = {
      http: {
        proxy: "http://proxy.example.com:8888",
        proxyStrictSSL: true,
      },
      telemetry: {
        telemetryLevel: "off",
      },
    };

    const client = new CopilotLanguageServerClient({
      rootUri: "file:///test",
      workspaceFolders: null,
      transport: mockTransport,
      copilotSettings,
    });

    expect(client).toBeDefined();
  });

  it("should send configuration after initialization when settings are provided", async () => {
    const copilotSettings = {
      http: {
        proxy: "http://proxy.example.com:8888",
        proxyStrictSSL: true,
      },
    };

    const client = new CopilotLanguageServerClient({
      rootUri: "file:///test",
      workspaceFolders: null,
      transport: mockTransport,
      copilotSettings,
    });

    // Spy on the notify method
    const notifySpy = vi.spyOn(client as any, "notify");

    // Wait for initialization
    await client.initializePromise;

    // Wait for next tick to let the configuration be sent
    await new Promise((resolve) => setTimeout(resolve, 0));

    // Verify that notify was called with the correct parameters
    expect(notifySpy).toHaveBeenCalledWith("workspace/didChangeConfiguration", {
      settings: copilotSettings,
    });
  });

  it("should not send configuration after initialization when settings are empty", async () => {
    const client = new CopilotLanguageServerClient({
      rootUri: "file:///test",
      workspaceFolders: null,
      transport: mockTransport,
      copilotSettings: {},
    });

    // Spy on the notify method
    const notifySpy = vi.spyOn(client as any, "notify");

    // Wait for initialization
    await client.initializePromise;

    // Wait for next tick
    await new Promise((resolve) => setTimeout(resolve, 0));

    // Verify that notify was NOT called with didChangeConfiguration
    expect(notifySpy).not.toHaveBeenCalledWith(
      "workspace/didChangeConfiguration",
      expect.anything(),
    );
  });

  it("should not send configuration after initialization when settings are not provided", async () => {
    const client = new CopilotLanguageServerClient({
      rootUri: "file:///test",
      workspaceFolders: null,
      transport: mockTransport,
    });

    // Spy on the notify method
    const notifySpy = vi.spyOn(client as any, "notify");

    // Wait for initialization
    await client.initializePromise;

    // Wait for next tick
    await new Promise((resolve) => setTimeout(resolve, 0));

    // Verify that notify was NOT called with didChangeConfiguration
    expect(notifySpy).not.toHaveBeenCalledWith(
      "workspace/didChangeConfiguration",
      expect.anything(),
    );
  });

  it("should accept github-enterprise settings", async () => {
    const copilotSettings = {
      "github-enterprise": {
        uri: "https://github.enterprise.com",
      },
    };

    const client = new CopilotLanguageServerClient({
      rootUri: "file:///test",
      workspaceFolders: null,
      transport: mockTransport,
      copilotSettings,
    });

    // Spy on the notify method
    const notifySpy = vi.spyOn(client as any, "notify");

    // Wait for initialization
    await client.initializePromise;

    // Wait for next tick to let the configuration be sent
    await new Promise((resolve) => setTimeout(resolve, 0));

    // Verify that notify was called with the enterprise settings
    expect(notifySpy).toHaveBeenCalledWith("workspace/didChangeConfiguration", {
      settings: copilotSettings,
    });
  });

  it("should accept all supported settings at once", async () => {
    const copilotSettings = {
      http: {
        proxy: "http://proxy.example.com:8888",
        proxyStrictSSL: true,
        proxyKerberosServicePrincipal: "HTTP/proxy.example.com",
      },
      telemetry: {
        telemetryLevel: "all",
      },
      "github-enterprise": {
        uri: "https://github.enterprise.com",
      },
    };

    const client = new CopilotLanguageServerClient({
      rootUri: "file:///test",
      workspaceFolders: null,
      transport: mockTransport,
      copilotSettings,
    });

    // Spy on the notify method
    const notifySpy = vi.spyOn(client as any, "notify");

    // Wait for initialization
    await client.initializePromise;

    // Wait for next tick to let the configuration be sent
    await new Promise((resolve) => setTimeout(resolve, 0));

    // Verify that notify was called with all settings
    expect(notifySpy).toHaveBeenCalledWith("workspace/didChangeConfiguration", {
      settings: copilotSettings,
    });
  });
});
