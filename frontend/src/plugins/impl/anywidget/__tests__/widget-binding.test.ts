/* Copyright 2026 Marimo. All rights reserved. */
import { beforeEach, describe, expect, it, vi } from "vitest";
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

  beforeEach(() => {
    registry = new WidgetDefRegistry();
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
    // The import will fail in Node (http: scheme not supported)
    await expect(promise1).rejects.toThrow();
    // After failure, cache should be cleared, so next call creates a new promise
    const promise2 = registry.getModule("http://localhost/a.js", "fail-hash");
    expect(promise1).not.toBe(promise2);
    promise2.catch(() => undefined);
  });
});

describe("WidgetBinding", () => {
  let binding: InstanceType<typeof WidgetBinding>;
  let model: Model<ModelState>;

  beforeEach(() => {
    binding = new WidgetBinding();
    model = new Model<ModelState>({ count: 0 }, createMockComm());
  });

  it("should initialize once and return a render function", async () => {
    const initCleanup = vi.fn();
    const renderCleanup = vi.fn();
    const widgetDef = {
      initialize: vi.fn().mockResolvedValue(initCleanup),
      render: vi.fn().mockResolvedValue(renderCleanup),
    };

    const renderFn = await binding.bind(widgetDef, model);
    expect(widgetDef.initialize).toHaveBeenCalledTimes(1);
    expect(typeof renderFn).toBe("function");

    // Render into an element
    const el = document.createElement("div");
    const controller = new AbortController();
    await renderFn(el, controller.signal);
    expect(widgetDef.render).toHaveBeenCalledTimes(1);
  });

  it("should return cached render for same widget def", async () => {
    const widgetDef = {
      initialize: vi.fn(),
      render: vi.fn(),
    };

    const render1 = await binding.bind(widgetDef, model);
    const render2 = await binding.bind(widgetDef, model);
    expect(render1).toBe(render2);
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

    const render1 = await binding.bind(widgetDef1, model);
    const render2 = await binding.bind(widgetDef2, model);

    expect(render1).not.toBe(render2);
    expect(cleanup1).toHaveBeenCalledTimes(1); // Old binding cleaned up
    expect(widgetDef2.initialize).toHaveBeenCalledTimes(1);
  });

  it("should cleanup render on view signal abort", async () => {
    const renderCleanup = vi.fn();
    const widgetDef = {
      initialize: vi.fn(),
      render: vi.fn().mockResolvedValue(renderCleanup),
    };

    const renderFn = await binding.bind(widgetDef, model);
    const el = document.createElement("div");
    const viewController = new AbortController();
    await renderFn(el, viewController.signal);

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

    const renderFn = await binding.bind(widgetDef, model);
    const el = document.createElement("div");
    const viewController = new AbortController();
    await renderFn(el, viewController.signal);

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
    const renderFn = await binding.bind(widgetDef, model);
    expect(typeof renderFn).toBe("function");

    // Render should not throw
    const el = document.createElement("div");
    const controller = new AbortController();
    await renderFn(el, controller.signal);
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
