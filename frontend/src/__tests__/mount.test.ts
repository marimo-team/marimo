/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { connectionAtom } from "@/core/network/connection";
import { store } from "@/core/state/jotai";
import { WebSocketState } from "@/core/websocket/types";
import { mount, visibleForTesting } from "../mount";

// Mock React DOM
vi.mock("react-dom/client", () => ({
  createRoot: vi.fn(() => ({
    render: vi.fn(),
  })),
}));

// Mock static state
vi.mock("@/core/static/static-state", () => ({
  isStaticNotebook: vi.fn(() => false),
}));

// Mock other side-effect modules
vi.mock("@/core/vscode/vscode-bindings", () => ({
  maybeRegisterVSCodeBindings: vi.fn(),
}));

vi.mock("@/plugins/plugins", () => ({
  initializePlugins: vi.fn(),
}));

vi.mock("@/core/network/auth", () => ({
  cleanupAuthQueryParams: vi.fn(),
}));

vi.mock("@/utils/vitals", () => ({
  reportVitals: vi.fn(),
}));

// Mock preloadPage
vi.mock("@/core/MarimoApp", () => ({
  MarimoApp: () => null,
  preloadPage: vi.fn(),
}));

describe("mount", () => {
  const mockElement = document.createElement("div");

  beforeEach(() => {
    visibleForTesting.reset();
    // Reset connection atom to initial state
    store.set(connectionAtom, { state: WebSocketState.NOT_STARTED });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  const baseOptions = {
    filename: "test.py",
    code: "",
    version: "0.0.1",
    mode: "edit" as const,
    config: {},
    configOverrides: {},
    appConfig: {},
    view: { showAppCode: true },
    serverToken: "",
  };

  describe("connection state initialization", () => {
    it("should set connection to CONNECTING when runtimeConfig has lazy=false", () => {
      mount(
        {
          ...baseOptions,
          runtimeConfig: [{ url: "http://localhost:8080", lazy: false }],
        },
        mockElement,
      );

      const connection = store.get(connectionAtom);
      expect(connection.state).toBe(WebSocketState.CONNECTING);
    });

    it("should keep connection as NOT_STARTED when runtimeConfig has lazy=true", () => {
      mount(
        {
          ...baseOptions,
          runtimeConfig: [{ url: "http://localhost:8080", lazy: true }],
        },
        mockElement,
      );

      const connection = store.get(connectionAtom);
      expect(connection.state).toBe(WebSocketState.NOT_STARTED);
    });

    it("should keep connection as NOT_STARTED when no runtimeConfig is provided", () => {
      mount(
        {
          ...baseOptions,
          runtimeConfig: [],
        },
        mockElement,
      );

      const connection = store.get(connectionAtom);
      expect(connection.state).toBe(WebSocketState.NOT_STARTED);
    });

    it("should keep connection as NOT_STARTED for static notebooks even with lazy=false", async () => {
      const { isStaticNotebook } = await import("@/core/static/static-state");
      vi.mocked(isStaticNotebook).mockReturnValue(true);

      // Reset mount state to allow another mount
      visibleForTesting.reset();

      mount(
        {
          ...baseOptions,
          runtimeConfig: [{ url: "http://localhost:8080", lazy: false }],
        },
        mockElement,
      );

      const connection = store.get(connectionAtom);
      expect(connection.state).toBe(WebSocketState.NOT_STARTED);
    });
  });
});
