/* Copyright 2026 Marimo. All rights reserved. */

import { beforeEach, describe, expect, expectTypeOf, it, vi } from "vitest";
import type * as MainModule from "../main";

// `main.ts` is the public islands entry point (see islands/vite.config.mts),
// so this suite snapshots its export surface + signatures and covers each
// entry point. The real bridge/bootstrap spin up a Web Worker and the plugin
// runtime, so we mock them.
const mockInitializeApps = vi.fn(() => Promise.resolve());
const mockStopSession = vi.fn((_appId?: string) => Promise.resolve());
const mockInitializeIslands = vi.fn(() => Promise.resolve());
const mockParseMarimoIslandApps = vi.fn(() => [] as Array<{ id: string }>);

vi.mock("@/core/islands/bridge", () => ({
  getGlobalBridge: () => ({
    initializeApps: mockInitializeApps,
    stopSession: mockStopSession,
  }),
}));

vi.mock("@/core/islands/bootstrap", () => ({
  initializeIslands: mockInitializeIslands,
}));

vi.mock("@/core/islands/parse", () => ({
  parseMarimoIslandApps: mockParseMarimoIslandApps,
}));

/**
 * Re-import a fresh copy of `main.ts` so the module-level `bootstrapPromise`
 * memoization does not leak between tests. The module auto-runs `initialize()`
 * on load, so we clear the DOM first to keep that a no-op.
 */
async function importMain(): Promise<typeof MainModule> {
  vi.resetModules();
  return import("../main");
}

beforeEach(() => {
  document.body.replaceChildren();
  mockInitializeApps.mockClear();
  mockStopSession.mockClear();
  mockInitializeIslands.mockClear();
  mockParseMarimoIslandApps.mockReset();
  mockParseMarimoIslandApps.mockReturnValue([]);
});

describe("islands public API surface", () => {
  it("exposes a stable set of exports and signatures", async () => {
    const mod = await importMain();
    const surface = Object.fromEntries(
      Object.keys(mod)
        .toSorted()
        .map((key) => {
          const value = (mod as Record<string, unknown>)[key];
          return [
            key,
            typeof value === "function"
              ? `function(arity ${value.length})`
              : typeof value,
          ];
        }),
    );

    expect(surface).toMatchInlineSnapshot(`
      {
        "canReplaceApp": "function(arity 0)",
        "initialize": "function(arity 0)",
        "stopApp": "function(arity 1)",
      }
    `);
  });

  it("matches the declared TypeScript signatures", () => {
    expectTypeOf<typeof MainModule.canReplaceApp>().toEqualTypeOf<
      () => boolean
    >();
    expectTypeOf<typeof MainModule.initialize>().toEqualTypeOf<
      () => Promise<void>
    >();
    expectTypeOf<typeof MainModule.stopApp>().toEqualTypeOf<
      (appId?: string) => Promise<void>
    >();
  });
});

describe("canReplaceApp", () => {
  it("returns false when the document has no island element", async () => {
    const mod = await importMain();

    expect(mod.canReplaceApp()).toBe(false);
    // Short-circuits on the DOM guard before parsing.
    expect(mockParseMarimoIslandApps).not.toHaveBeenCalled();
  });

  it("returns true for exactly one app without materializing the DOM", async () => {
    const mod = await importMain();
    document.body.innerHTML = `<marimo-island data-app-id="app-1"></marimo-island>`;
    mockParseMarimoIslandApps.mockReturnValue([{ id: "app-1" }]);

    expect(mod.canReplaceApp()).toBe(true);
    // A probe must not mutate island attributes.
    expect(mockParseMarimoIslandApps).toHaveBeenCalledWith(document, {
      materialize: false,
    });
  });

  it("returns false when more than one app is present", async () => {
    const mod = await importMain();
    document.body.innerHTML = `<marimo-island data-app-id="app-1"></marimo-island>`;
    mockParseMarimoIslandApps.mockReturnValue([
      { id: "app-1" },
      { id: "app-2" },
    ]);

    expect(mod.canReplaceApp()).toBe(false);
  });

  it("returns false when the island parses into zero apps", async () => {
    const mod = await importMain();
    document.body.innerHTML = `<marimo-island></marimo-island>`;
    mockParseMarimoIslandApps.mockReturnValue([]);

    expect(mod.canReplaceApp()).toBe(false);
  });
});

describe("stopApp", () => {
  it("forwards the requested app id to the bridge", async () => {
    const mod = await importMain();

    await mod.stopApp("app-7");
    expect(mockStopSession).toHaveBeenCalledWith("app-7");

    await mod.stopApp();
    expect(mockStopSession).toHaveBeenLastCalledWith(undefined);
  });
});

describe("initialize", () => {
  it("skips bootstrap and app start when no islands are present", async () => {
    const mod = await importMain();

    await mod.initialize();

    expect(mockInitializeIslands).not.toHaveBeenCalled();
    expect(mockInitializeApps).not.toHaveBeenCalled();
  });

  it("bootstraps once, marks islands, and starts apps on each call", async () => {
    const mod = await importMain();
    document.body.innerHTML = `<marimo-island></marimo-island>`;

    await mod.initialize();
    await mod.initialize();

    expect(mockInitializeIslands).toHaveBeenCalledOnce();
    expect(mockInitializeApps).toHaveBeenCalledTimes(2);
    expect(
      document.querySelector("marimo-island")?.classList.contains("marimo"),
    ).toBe(true);
  });

  it("clears the memoized bootstrap when it fails so it can be retried", async () => {
    const mod = await importMain();
    document.body.innerHTML = `<marimo-island></marimo-island>`;
    mockInitializeIslands.mockRejectedValueOnce(new Error("bootstrap failed"));

    await expect(mod.initialize()).rejects.toThrow("bootstrap failed");
    await mod.initialize();

    expect(mockInitializeIslands).toHaveBeenCalledTimes(2);
    expect(mockInitializeApps).toHaveBeenCalledOnce();
  });
});
