/* Copyright 2026 Marimo. All rights reserved. */
import type { ExtractAtomValue } from "jotai";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { hasRunAnyCellAtom } from "@/components/editor/cell/useRunCells";
import { userConfigAtom } from "@/core/config/config";
import { parseUserConfig } from "@/core/config/config-schema";
import { initialModeAtom } from "@/core/mode";
import { store } from "@/core/state/jotai";
import { Model } from "../model";
import type { ModelState, WidgetModelId } from "../types";
import { visibleForTesting } from "../widget-binding";

const { WidgetDefRegistry, WidgetBinding, BindingManager } = visibleForTesting;

// Helper to create typed model IDs for tests
const asModelId = (id: string): WidgetModelId => id as WidgetModelId;

function createMockComm() {
  return {
    sendUpdate: vi.fn().mockResolvedValue(undefined),
    sendCustomMessage: vi.fn().mockResolvedValue(undefined),
  };
}

describe("WidgetDefRegistry", () => {
  let registry: InstanceType<typeof WidgetDefRegistry>;
  let previousConfig: ExtractAtomValue<typeof userConfigAtom>;
  let previousMode: ExtractAtomValue<typeof initialModeAtom>;
  let previousHasRunAnyCell: ExtractAtomValue<typeof hasRunAnyCellAtom>;

  beforeEach(() => {
    registry = new WidgetDefRegistry();
    // Force "no notebook trust" so the `data:` rejection test below
    // exercises the untrusted branch. The positive trust path is covered
    // centrally in trusted-url.test.ts.
    previousConfig = store.get(userConfigAtom);
    previousMode = store.get(initialModeAtom);
    previousHasRunAnyCell = store.get(hasRunAnyCellAtom);
    store.set(hasRunAnyCellAtom, false);
    const cleared = parseUserConfig({});
    store.set(userConfigAtom, {
      ...cleared,
      runtime: { ...cleared.runtime, auto_instantiate: false },
    });
    store.set(initialModeAtom, "edit");
  });

  afterEach(() => {
    store.set(userConfigAtom, previousConfig);
    store.set(initialModeAtom, previousMode);
    store.set(hasRunAnyCellAtom, previousHasRunAnyCell);
  });

  it("should cache modules by jsHash and return same promise", () => {
    // Two calls with same hash should return the exact same promise object
    const promise1 = registry.getModule("http://localhost/widget.js", "hash1");
    const promise2 = registry.getModule("http://localhost/widget.js", "hash1");
    expect(promise1).toBe(promise2);
    // Catch the unhandled rejection from the import() attempt
    promise1.catch(() => undefined);
  });

  it("should deduplicate concurrent imports for the same hash", () => {
    const promise1 = registry.getModule("http://localhost/a.js", "same-hash");
    const promise2 = registry.getModule("http://localhost/b.js", "same-hash");
    // Same hash means same promise, even with different URLs
    expect(promise1).toBe(promise2);
    promise1.catch(() => undefined);
  });

  it("should create different promises for different hashes", () => {
    const promise1 = registry.getModule("http://localhost/a.js", "hash-a");
    const promise2 = registry.getModule("http://localhost/b.js", "hash-b");
    expect(promise1).not.toBe(promise2);
    promise1.catch(() => undefined);
    promise2.catch(() => undefined);
  });

  it("should invalidate cached modules", () => {
    const promise1 = registry.getModule("http://localhost/a.js", "hash1");
    promise1.catch(() => undefined);
    registry.invalidate("hash1");
    const promise2 = registry.getModule("http://localhost/a.js", "hash1");
    promise2.catch(() => undefined);
    expect(promise1).not.toBe(promise2);
  });

  it("should remove from cache on import failure so retry creates new promise", async () => {
    const promise1 = registry.getModule("http://localhost/a.js", "fail-hash");
    // The URL is rejected by the trusted-URL validator.
    await expect(promise1).rejects.toThrow();
    // After failure, cache should be cleared, so next call creates a new promise
    const promise2 = registry.getModule("http://localhost/a.js", "fail-hash");
    expect(promise1).not.toBe(promise2);
    promise2.catch(() => undefined);
  });

  describe("URL validation", () => {
    it.each([
      // Attack vector: raw <marimo-anywidget data-js-url=...> in markdown
      "http://127.0.0.1:8820/poc.mjs",
      "https://evil.example.com/widget.mjs",
      "//evil.example.com/widget.mjs",
      "javascript:alert(1)",
      "data:text/javascript;base64,YWxlcnQoMSk=",
      "./@file/x.js?redirect=http://evil.com",
      "",
    ])("rejects untrusted URL: %s", async (url) => {
      await expect(registry.getModule(url, `hash-${url}`)).rejects.toThrow(
        /untrusted/i,
      );
    });

    it("accepts virtual file paths (fails later at import time)", async () => {
      // The URL passes validation but the import still fails because this
      // is a Node test environment with no server. We only assert that
      // the rejection reason is NOT the "untrusted URL" refusal.
      await expect(
        registry.getModule("./@file/123-widget.js", "trusted-hash"),
      ).rejects.not.toThrow(/untrusted/i);
    });
  });
});

describe("WidgetBinding", () => {
  let binding: InstanceType<typeof WidgetBinding>;
  let model: Model<ModelState>;

  beforeEach(() => {
    binding = new WidgetBinding();
    model = new Model<ModelState>({ count: 0 }, createMockComm());
  });

  it("should initialize once per bind and run render once per createView", async () => {
    const initCleanup = vi.fn();
    const renderCleanup = vi.fn();
    const widgetDef = {
      initialize: vi.fn().mockResolvedValue(initCleanup),
      render: vi.fn().mockResolvedValue(renderCleanup),
    };

    await binding.bind(widgetDef, model);
    expect(widgetDef.initialize).toHaveBeenCalledTimes(1);

    const el = document.createElement("div");
    const controller = new AbortController();
    await binding.createView({ el }, { signal: controller.signal });
    expect(widgetDef.render).toHaveBeenCalledTimes(1);
  });

  it("should not re-initialize on a redundant bind with the same widget def", async () => {
    const widgetDef = {
      initialize: vi.fn(),
      render: vi.fn(),
    };

    await binding.bind(widgetDef, model);
    await binding.bind(widgetDef, model);
    // Initialize should only be called once
    expect(widgetDef.initialize).toHaveBeenCalledTimes(1);
  });

  it("should re-initialize on hot reload (different widget def)", async () => {
    const cleanup1 = vi.fn();
    const widgetDef1 = {
      initialize: vi.fn().mockResolvedValue(cleanup1),
      render: vi.fn(),
    };

    const widgetDef2 = {
      initialize: vi.fn(),
      render: vi.fn(),
    };

    await binding.bind(widgetDef1, model);
    await binding.bind(widgetDef2, model);

    expect(cleanup1).toHaveBeenCalledTimes(1); // Old binding cleaned up
    expect(widgetDef2.initialize).toHaveBeenCalledTimes(1);
  });

  it("should cleanup render on view signal abort", async () => {
    const renderCleanup = vi.fn();
    const widgetDef = {
      initialize: vi.fn(),
      render: vi.fn().mockResolvedValue(renderCleanup),
    };

    await binding.bind(widgetDef, model);
    const el = document.createElement("div");
    const viewController = new AbortController();
    await binding.createView({ el }, { signal: viewController.signal });

    // Aborting the view signal should trigger render cleanup
    viewController.abort();
    expect(renderCleanup).toHaveBeenCalledTimes(1);
  });

  it("should cleanup everything on destroy", async () => {
    const initCleanup = vi.fn();
    const renderCleanup = vi.fn();
    const widgetDef = {
      initialize: vi.fn().mockResolvedValue(initCleanup),
      render: vi.fn().mockResolvedValue(renderCleanup),
    };

    await binding.bind(widgetDef, model);
    const el = document.createElement("div");
    const viewController = new AbortController();
    await binding.createView({ el }, { signal: viewController.signal });

    binding.destroy();
    expect(initCleanup).toHaveBeenCalledTimes(1);
    expect(renderCleanup).toHaveBeenCalledTimes(1);
  });

  it("should handle widget def as a function", async () => {
    const widget = {
      initialize: vi.fn(),
      render: vi.fn(),
    };
    const widgetDefFn = vi.fn().mockResolvedValue(widget);

    await binding.bind(widgetDefFn, model);
    expect(widgetDefFn).toHaveBeenCalledTimes(1);
    expect(widget.initialize).toHaveBeenCalledTimes(1);
  });

  it("should handle widget with no initialize or render", async () => {
    const widgetDef = {};
    await binding.bind(widgetDef, model);

    // createView should be a no-op rather than throw
    const el = document.createElement("div");
    const controller = new AbortController();
    await binding.createView({ el }, { signal: controller.signal });
  });

  it("should pass an AbortSignal to initialize that aborts on destroy", async () => {
    const widgetDef = {
      initialize: vi.fn(),
      render: vi.fn(),
    };

    await binding.bind(widgetDef, model);

    expect(widgetDef.initialize).toHaveBeenCalledTimes(1);
    const initProps = widgetDef.initialize.mock.calls[0][0];
    expect(initProps.signal).toBeInstanceOf(AbortSignal);
    expect(initProps.signal.aborted).toBe(false);

    binding.destroy();
    expect(initProps.signal.aborted).toBe(true);
  });

  it("should pass an AbortSignal to initialize that aborts on hot reload", async () => {
    const widgetDef1 = {
      initialize: vi.fn(),
      render: vi.fn(),
    };
    const widgetDef2 = {
      initialize: vi.fn(),
      render: vi.fn(),
    };

    await binding.bind(widgetDef1, model);
    const firstSignal = widgetDef1.initialize.mock.calls[0][0].signal;
    expect(firstSignal.aborted).toBe(false);

    await binding.bind(widgetDef2, model);
    expect(firstSignal.aborted).toBe(true);

    const secondSignal = widgetDef2.initialize.mock.calls[0][0].signal;
    expect(secondSignal).not.toBe(firstSignal);
    expect(secondSignal.aborted).toBe(false);
  });

  it("should pass a combined AbortSignal to render that aborts on view unmount", async () => {
    const widgetDef = {
      initialize: vi.fn(),
      render: vi.fn(),
    };

    await binding.bind(widgetDef, model);
    const el = document.createElement("div");
    const viewController = new AbortController();
    await binding.createView({ el }, { signal: viewController.signal });

    const renderProps = widgetDef.render.mock.calls[0][0];
    expect(renderProps.signal).toBeInstanceOf(AbortSignal);
    expect(renderProps.signal.aborted).toBe(false);

    viewController.abort();
    expect(renderProps.signal.aborted).toBe(true);
  });

  it("should pass a render signal that also aborts on binding destroy", async () => {
    const widgetDef = {
      initialize: vi.fn(),
      render: vi.fn(),
    };

    await binding.bind(widgetDef, model);
    const el = document.createElement("div");
    const viewController = new AbortController();
    await binding.createView({ el }, { signal: viewController.signal });

    const renderProps = widgetDef.render.mock.calls[0][0];
    expect(renderProps.signal.aborted).toBe(false);

    binding.destroy();
    expect(renderProps.signal.aborted).toBe(true);
  });

  it("should auto-clear listeners registered through model when render signal aborts", async () => {
    // The model passed to render is a `modelProxy` that auto-ties on()
    // calls to the render signal — so a widget that just calls
    // model.on(...) without explicit cleanup gets it for free.
    const cb = vi.fn();
    const widgetDef = {
      initialize: vi.fn(),
      render: vi.fn(({ model: m }) => {
        m.on("change:count", cb);
      }),
    };

    await binding.bind(widgetDef, model);
    const viewController = new AbortController();
    await binding.createView(
      { el: document.createElement("div") },
      { signal: viewController.signal },
    );

    model.set("count", 1);
    expect(cb).toHaveBeenCalledTimes(1);

    viewController.abort();
    model.set("count", 2);
    expect(cb).toHaveBeenCalledTimes(1);
  });

  it("should auto-clear listeners registered through model in initialize on hot reload", async () => {
    const cb = vi.fn();
    const widgetDef1 = {
      initialize: vi.fn(({ model: m }) => {
        m.on("change:count", cb);
      }),
      render: vi.fn(),
    };
    const widgetDef2 = {
      initialize: vi.fn(),
      render: vi.fn(),
    };

    await binding.bind(widgetDef1, model);
    model.set("count", 1);
    expect(cb).toHaveBeenCalledTimes(1);

    await binding.bind(widgetDef2, model);
    model.set("count", 2);
    expect(cb).toHaveBeenCalledTimes(1);
  });

  it("should expose exports from initialize via `ready` and `exports`", async () => {
    const exports = { getValue: () => 42 };
    const widgetDef = {
      initialize: vi.fn().mockResolvedValue(exports),
      render: vi.fn(),
    };

    await binding.bind(widgetDef, model);

    await expect(binding.ready).resolves.toBe(exports);
    expect(binding.exports).toBe(exports);
  });

  it("should resolve `ready` with undefined when initialize returns void", async () => {
    const widgetDef = {
      initialize: vi.fn(),
      render: vi.fn(),
    };

    await binding.bind(widgetDef, model);

    await expect(binding.ready).resolves.toBeUndefined();
    expect(binding.exports).toBeUndefined();
  });

  it("should resolve `ready` with undefined when initialize returns a cleanup function", async () => {
    const cleanup = vi.fn();
    const widgetDef = {
      initialize: vi.fn().mockResolvedValue(cleanup),
      render: vi.fn(),
    };

    await binding.bind(widgetDef, model);

    await expect(binding.ready).resolves.toBeUndefined();
    expect(binding.exports).toBeUndefined();
    // Cleanup is still wired to abort
    binding.destroy();
    expect(cleanup).toHaveBeenCalledTimes(1);
  });

  it("should reject `ready` and re-create it on hot reload", async () => {
    const widgetDef1 = {
      initialize: vi.fn().mockResolvedValue({ id: 1 }),
      render: vi.fn(),
    };
    const widgetDef2 = {
      initialize: vi.fn().mockResolvedValue({ id: 2 }),
      render: vi.fn(),
    };

    await binding.bind(widgetDef1, model);
    const firstReady = binding.ready;
    await expect(firstReady).resolves.toEqual({ id: 1 });

    await binding.bind(widgetDef2, model);
    const secondReady = binding.ready;

    expect(secondReady).not.toBe(firstReady);
    await expect(secondReady).resolves.toEqual({ id: 2 });
    expect(binding.exports).toEqual({ id: 2 });
  });

  it("should reject `ready` if hot reload happens while initialize is in flight", async () => {
    let resolveInit!: (v: object) => void;
    const widgetDef1 = {
      initialize: vi.fn().mockReturnValue(
        new Promise<object>((r) => {
          resolveInit = r;
        }),
      ),
      render: vi.fn(),
    };
    const widgetDef2 = {
      initialize: vi.fn().mockResolvedValue({ id: 2 }),
      render: vi.fn(),
    };

    const bindPromise1 = binding.bind(widgetDef1, model);
    const firstReady = binding.ready;
    // Suppress unhandled rejection of the captured promise — we assert it
    // rejects below.
    firstReady.catch(() => undefined);

    await binding.bind(widgetDef2, model);

    await expect(firstReady).rejects.toThrow(/aborted by re-bind/);

    // The first widget's initialize eventually resolves but its result is
    // discarded because the binding signal is aborted.
    resolveInit({ id: 1 });
    await bindPromise1;
    expect(binding.exports).toEqual({ id: 2 });
  });

  it("should reject `ready` on destroy", async () => {
    // Don't resolve initialize — simulate a destroy mid-flight.
    const widgetDef = {
      initialize: vi.fn().mockReturnValue(new Promise(() => undefined)),
      render: vi.fn(),
    };

    void binding.bind(widgetDef, model);
    const ready = binding.ready;
    ready.catch(() => undefined);

    binding.destroy();

    await expect(ready).rejects.toThrow(/binding destroyed/);
  });
});

describe("BindingManager", () => {
  let manager: InstanceType<typeof BindingManager>;

  beforeEach(() => {
    manager = new BindingManager();
  });

  it("should create bindings on demand", () => {
    const modelId = asModelId("model-1");
    expect(manager.has(modelId)).toBe(false);

    const binding = manager.getOrCreate(modelId);
    expect(binding).toBeDefined();
    expect(manager.has(modelId)).toBe(true);
  });

  it("should return the same binding for the same model id", () => {
    const modelId = asModelId("model-1");
    const binding1 = manager.getOrCreate(modelId);
    const binding2 = manager.getOrCreate(modelId);
    expect(binding1).toBe(binding2);
  });

  it("should destroy and remove bindings", async () => {
    const modelId = asModelId("model-1");
    const binding = manager.getOrCreate(modelId);

    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    const initCleanup = vi.fn();
    const widgetDef = {
      initialize: vi.fn().mockResolvedValue(initCleanup),
      render: vi.fn(),
    };
    await binding.bind(widgetDef, model);

    manager.destroy(modelId);
    expect(manager.has(modelId)).toBe(false);
    expect(initCleanup).toHaveBeenCalledTimes(1);
  });

  it("should handle idempotent destroy", () => {
    const modelId = asModelId("model-1");
    manager.getOrCreate(modelId);

    // Should not throw
    manager.destroy(modelId);
    manager.destroy(modelId);
    expect(manager.has(modelId)).toBe(false);
  });
});
