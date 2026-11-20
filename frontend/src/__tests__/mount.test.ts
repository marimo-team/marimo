/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getSerializedLayout } from "@/core/layout/layout";
import { initialLayoutState, layoutStateAtom } from "@/core/layout/state";
import { kioskModeAtom } from "@/core/mode";
import { runtimeConfigAtom } from "@/core/runtime/config";
import { RuntimeManager } from "@/core/runtime/runtime";
import { store } from "@/core/state/jotai";
import { isStaticNotebook } from "@/core/static/static-state";
import { pairConfigAtom } from "@/core/config/pair";
import { PAIR_CONFIG } from "./fixtures/pair-config";
import { mount, visibleForTesting } from "../mount";

// Mock React DOM
vi.mock("react-dom/client", () => ({
  createRoot: vi.fn(() => ({
    render: vi.fn(),
  })),
}));

// Mock static state
vi.mock("@/core/static/static-state", () => ({
  getStaticModelNotifications: vi.fn(() => undefined),
  getStaticVirtualFiles: vi.fn(() => ({})),
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
    window.history.replaceState({}, "", "/");
    vi.mocked(isStaticNotebook).mockReturnValue(false);
    store.set(layoutStateAtom, initialLayoutState());
    store.set(kioskModeAtom, false);
    vi.spyOn(RuntimeManager.prototype, "init").mockResolvedValue(undefined);
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

  const mountRead = (options: Record<string, unknown> = {}) =>
    mount(
      { ...baseOptions, mode: "read", runtimeConfig: [], ...options },
      mockElement,
    );

  it("hydrates the server's Pair configuration", () => {
    const error = mountRead({ pairConfig: PAIR_CONFIG });

    expect(error).toBeUndefined();
    expect(store.get(pairConfigAtom)).toEqual(PAIR_CONFIG);
  });

  it("clears Pair configuration when the server omits it", () => {
    store.set(pairConfigAtom, PAIR_CONFIG);

    const error = mountRead();

    expect(error).toBeUndefined();
    expect(store.get(pairConfigAtom)).toBeUndefined();
  });

  it("starts looking for the page's runtime", () => {
    mountRead();

    expect(RuntimeManager.prototype.init).toHaveBeenCalledOnce();
  });

  it("accepts a runtime config that still carries `lazy`", () => {
    const error = mount(
      {
        ...baseOptions,
        runtimeConfig: [{ url: "http://localhost:8080", lazy: true }],
      },
      mockElement,
    );

    expect(error).toBeUndefined();
    expect(store.get(runtimeConfigAtom).url).toBe("http://localhost:8080");
  });

  it("hydrates the layout embedded in the mount config", () => {
    const layout = {
      type: "slides",
      data: {
        deck: { transition: "fade", verticalAlign: "center" },
      },
    };
    const error = mountRead({ layout });

    expect(error).toBeUndefined();
    const layoutState = store.get(layoutStateAtom);
    expect(layoutState.selectedLayout).toBe("slides");
    expect(getSerializedLayout()).toEqual({
      type: "slides",
      data: {
        cells: [],
        deck: { transition: "fade", verticalAlign: "center" },
      },
    });
  });

  it("uses vertical layout for malformed mount data", () => {
    const error = mountRead({ layout: { data: {} } });

    expect(error).toBeUndefined();
    expect(store.get(layoutStateAtom)).toEqual(initialLayoutState());
  });

  it("starts kiosk clients in kiosk mode", () => {
    window.history.replaceState({}, "", "/?kiosk=true");

    const error = mountRead();

    expect(error).toBeUndefined();
    expect(store.get(kioskModeAtom)).toBe(true);
  });
});
