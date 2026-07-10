/* Copyright 2026 Marimo. All rights reserved. */
import type { ExtractAtomValue } from "jotai";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AnyWidget } from "@anywidget/types";
import { hasRunAnyCellAtom } from "@/components/editor/cell/useRunCells";
import { userConfigAtom } from "@/core/config/config";
import { parseUserConfig } from "@/core/config/config-schema";
import { initialModeAtom } from "@/core/mode";
import { store } from "@/core/state/jotai";
import { Model } from "../model";
import type { Host } from "../host";
import type { ModelState } from "../types";
import { visibleForTesting } from "../widget-binding";

const { WidgetDefRegistry, WidgetBinding } = visibleForTesting;

function createMockComm() {
  return {
    sendUpdate: vi.fn().mockResolvedValue(undefined),
    sendCustomMessage: vi.fn().mockResolvedValue(undefined),
  };
}

const createTestHost = (): Host => ({
  getModel: vi.fn(),
  getWidget: vi.fn(),
});

// oxlint-disable-next-line marimo/prefer-object-params -- terse test helper
function createBinding<T extends ModelState>(
  widgetDef: AnyWidget<T>,
  model: Model<T>,
  options: { controller?: AbortController } = {},
) {
  return WidgetBinding.create({
    widgetDef,
    model,
    createHost: createTestHost,
    controller: options.controller,
  });
}

// oxlint-disable-next-line marimo/prefer-object-params -- terse test helper
function getModule(
  registry: InstanceType<typeof WidgetDefRegistry>,
  jsUrl: string,
  jsHash: string,
) {
  return registry.getModule({ jsUrl, jsHash });
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
    const promise1 = getModule(registry, "http://localhost/widget.js", "hash1");
    const promise2 = getModule(registry, "http://localhost/widget.js", "hash1");
    expect(promise1).toBe(promise2);
    // Catch the unhandled rejection from the import() attempt
    promise1.catch(() => undefined);
  });

  it("should deduplicate concurrent imports for the same hash", () => {
    const promise1 = getModule(registry, "http://localhost/a.js", "same-hash");
    const promise2 = getModule(registry, "http://localhost/b.js", "same-hash");
    // Same hash means same promise, even with different URLs
    expect(promise1).toBe(promise2);
    promise1.catch(() => undefined);
  });

  it("should create different promises for different hashes", () => {
    const promise1 = getModule(registry, "http://localhost/a.js", "hash-a");
    const promise2 = getModule(registry, "http://localhost/b.js", "hash-b");
    expect(promise1).not.toBe(promise2);
    promise1.catch(() => undefined);
    promise2.catch(() => undefined);
  });

  it("should remove from cache on import failure so retry creates new promise", async () => {
    const promise1 = getModule(registry, "http://localhost/a.js", "fail-hash");
    // The URL is rejected by the trusted-URL validator.
    await expect(promise1).rejects.toThrow();
    // After failure, cache should be cleared, so next call creates a new promise
    const promise2 = getModule(registry, "http://localhost/a.js", "fail-hash");
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
      await expect(getModule(registry, url, `hash-${url}`)).rejects.toThrow(
        /untrusted/i,
      );
    });

    it("accepts virtual file paths (fails later at import time)", async () => {
      // The URL passes validation but the import still fails because this
      // is a Node test environment with no server. We only assert that
      // the rejection reason is NOT the "untrusted URL" refusal.
      await expect(
        getModule(registry, "./@file/123-widget.js", "trusted-hash"),
      ).rejects.not.toThrow(/untrusted/i);
    });
  });
});

describe("WidgetBinding", () => {
  it("should run initialize exactly once and expose exports", async () => {
    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    const exports = { setValue: vi.fn() };
    const widgetDef = {
      initialize: vi.fn().mockResolvedValue(exports),
      render: vi.fn(),
    };

    const binding = await createBinding(widgetDef, model);
    expect(widgetDef.initialize).toHaveBeenCalledTimes(1);
    expect(binding.exports).toBe(exports);

    const controller = new AbortController();
    await binding.createView(
      { el: document.createElement("div") },
      { signal: controller.signal },
    );
    await binding.createView(
      { el: document.createElement("div") },
      { signal: controller.signal },
    );
    expect(widgetDef.initialize).toHaveBeenCalledTimes(1);
    expect(widgetDef.render).toHaveBeenCalledTimes(2);
  });

  it("should handle widget def as a factory function", async () => {
    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    const render = vi.fn();
    const factory = vi.fn().mockResolvedValue({ render });

    const binding = await createBinding(factory, model);
    const controller = new AbortController();
    await binding.createView(
      { el: document.createElement("div") },
      { signal: controller.signal },
    );
    expect(factory).toHaveBeenCalledTimes(1);
    expect(render).toHaveBeenCalledTimes(1);
  });

  it("should handle a widget with no initialize or render", async () => {
    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    const binding = await createBinding({}, model);
    expect(binding.exports).toBeUndefined();
    const controller = new AbortController();
    // No render — createView is a no-op, not an error.
    await binding.createView(
      { el: document.createElement("div") },
      { signal: controller.signal },
    );
  });

  it("should expose undefined exports for void initialize", async () => {
    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    const binding = await createBinding(
      { initialize: vi.fn(), render: vi.fn() },
      model,
    );
    expect(binding.exports).toBeUndefined();
  });

  it("should run a legacy initialize cleanup on destroy", async () => {
    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    const initCleanup = vi.fn();
    const binding = await createBinding(
      { initialize: vi.fn().mockResolvedValue(initCleanup), render: vi.fn() },
      model,
    );
    expect(binding.exports).toBeUndefined();
    expect(initCleanup).not.toHaveBeenCalled();
    binding.destroy();
    expect(initCleanup).toHaveBeenCalledTimes(1);
  });

  it("should reject and run cleanup when aborted mid-initialize", async () => {
    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    const initCleanup = vi.fn();
    let resolveInit!: (v: unknown) => void;
    const widgetDef = {
      initialize: vi.fn().mockReturnValue(
        new Promise((r) => {
          resolveInit = r;
        }),
      ),
      render: vi.fn(),
    };

    const controller = new AbortController();
    const pending = createBinding(widgetDef, model, { controller });
    pending.catch(() => undefined);

    controller.abort();
    resolveInit(initCleanup);

    await expect(pending).rejects.toThrow(/binding destroyed/);
    expect(initCleanup).toHaveBeenCalledTimes(1);
  });

  it("should pass an AbortSignal to initialize that aborts on destroy", async () => {
    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    const widgetDef = { initialize: vi.fn(), render: vi.fn() };
    const binding = await createBinding(widgetDef, model);

    const initSignal = widgetDef.initialize.mock.calls[0][0]
      .signal as AbortSignal;
    expect(initSignal.aborted).toBe(false);
    binding.destroy();
    expect(initSignal.aborted).toBe(true);
  });

  it("should abort a view when its own signal aborts", async () => {
    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    const renderCleanup = vi.fn();
    const widgetDef = {
      render: vi.fn().mockResolvedValue(renderCleanup),
    };
    const binding = await createBinding(widgetDef, model);

    const controller = new AbortController();
    await binding.createView(
      { el: document.createElement("div") },
      { signal: controller.signal },
    );
    const renderSignal = widgetDef.render.mock.calls[0][0]
      .signal as AbortSignal;
    expect(renderSignal.aborted).toBe(false);

    controller.abort();
    expect(renderSignal.aborted).toBe(true);
    expect(renderCleanup).toHaveBeenCalledTimes(1);
  });

  it("runs a late render cleanup after the view already aborted", async () => {
    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    const renderCleanup = vi.fn();
    let resolveRender!: (cleanup: () => void) => void;
    const widgetDef = {
      render: vi.fn(
        () =>
          new Promise<() => void>((resolve) => {
            resolveRender = resolve;
          }),
      ),
    };
    const binding = await createBinding(widgetDef, model);
    const controller = new AbortController();

    const pending = binding.createView(
      { el: document.createElement("div") },
      { signal: controller.signal },
    );
    controller.abort();
    resolveRender(renderCleanup);

    await pending;
    expect(renderCleanup).toHaveBeenCalledTimes(1);
  });

  it("should abort every view when the binding is destroyed", async () => {
    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    const renderCleanup = vi.fn();
    const widgetDef = {
      render: vi.fn().mockResolvedValue(renderCleanup),
    };
    const binding = await createBinding(widgetDef, model);

    const controller = new AbortController();
    await binding.createView(
      { el: document.createElement("div") },
      { signal: controller.signal },
    );
    const renderSignal = widgetDef.render.mock.calls[0][0]
      .signal as AbortSignal;

    binding.destroy();
    expect(renderSignal.aborted).toBe(true);
    expect(renderCleanup).toHaveBeenCalledTimes(1);
    // The caller's own signal is untouched — only the combined one.
    expect(controller.signal.aborted).toBe(false);
  });

  it("should auto-clear render listeners when the view aborts", async () => {
    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    const onCount = vi.fn();
    const widgetDef = {
      render: vi.fn(({ model }) => {
        model.on("change:count", onCount);
      }),
    };
    const binding = await createBinding(widgetDef, model);

    const controller = new AbortController();
    await binding.createView(
      { el: document.createElement("div") },
      { signal: controller.signal },
    );
    // Called once by the hydration replay at mount, once by the set.
    model.set("count", 1);
    expect(onCount).toHaveBeenCalledTimes(2);

    controller.abort();
    model.set("count", 2);
    expect(onCount).toHaveBeenCalledTimes(2);
  });

  it("should auto-clear initialize listeners on destroy", async () => {
    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    const onCount = vi.fn();
    const widgetDef = {
      initialize: vi.fn(({ model }) => {
        model.on("change:count", onCount);
      }),
      render: vi.fn(),
    };
    const binding = await createBinding(widgetDef, model);

    model.set("count", 1);
    expect(onCount).toHaveBeenCalledTimes(1);

    binding.destroy();
    model.set("count", 2);
    expect(onCount).toHaveBeenCalledTimes(1);
  });
});

describe("WidgetBinding hydration replay", () => {
  it("replays current state to render listeners exactly once", async () => {
    const model = new Model<ModelState>({ count: 8 }, createMockComm());
    const el = document.createElement("div");
    const widgetDef = {
      render: vi.fn(({ model, el }) => {
        // A widget view that starts with a local default and relies on
        // change events for hydration.
        el.textContent = "count is 5";
        model.on("change:count", () => {
          el.textContent = `count is ${model.get("count")}`;
        });
      }),
    };
    const binding = await createBinding(widgetDef, model);

    const controller = new AbortController();
    await binding.createView({ el }, { signal: controller.signal });
    expect(el.textContent).toBe("count is 8");
  });

  it("does not re-fire listeners of already-mounted views", async () => {
    // Mounting view B must not double-paint view A: the replay is
    // scoped to the listeners the new render attached.
    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    const listeners: Array<ReturnType<typeof vi.fn>> = [];
    const widgetDef = {
      render: vi.fn(({ model }) => {
        const listener = vi.fn();
        listeners.push(listener);
        model.on("change:count", listener);
      }),
    };
    const binding = await createBinding(widgetDef, model);
    const controller = new AbortController();

    await binding.createView(
      { el: document.createElement("div") },
      { signal: controller.signal },
    );
    expect(listeners[0]).toHaveBeenCalledTimes(1);

    await binding.createView(
      { el: document.createElement("div") },
      { signal: controller.signal },
    );
    // View B's listener hydrated once; view A's was left alone.
    expect(listeners[1]).toHaveBeenCalledTimes(1);
    expect(listeners[0]).toHaveBeenCalledTimes(1);
  });

  it("replays the any-change event to its listeners", async () => {
    const model = new Model<ModelState>({ count: 1 }, createMockComm());
    const onAnyChange = vi.fn();
    const widgetDef = {
      render: vi.fn(({ model }) => {
        model.on("change", onAnyChange);
      }),
    };
    const binding = await createBinding(widgetDef, model);
    const controller = new AbortController();
    await binding.createView(
      { el: document.createElement("div") },
      { signal: controller.signal },
    );
    expect(onAnyChange).toHaveBeenCalledTimes(1);
  });

  it("does not replay initialize listeners", async () => {
    // The guarantee is per-view: initialize listeners existed before
    // any view, and replaying at them would fire once per mount.
    const model = new Model<ModelState>({ count: 1 }, createMockComm());
    const initListener = vi.fn();
    const widgetDef = {
      initialize: vi.fn(({ model }) => {
        model.on("change:count", initListener);
      }),
      render: vi.fn(),
    };
    const binding = await createBinding(widgetDef, model);
    const controller = new AbortController();
    await binding.createView(
      { el: document.createElement("div") },
      { signal: controller.signal },
    );
    expect(initListener).not.toHaveBeenCalled();
  });

  it("clears the element before rendering into it", async () => {
    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    const el = document.createElement("div");
    el.innerHTML = "<span>stale content</span>";
    const binding = await createBinding({ render: vi.fn() }, model);
    const controller = new AbortController();
    await binding.createView({ el }, { signal: controller.signal });
    expect(el.innerHTML).toBe("");
  });
});
