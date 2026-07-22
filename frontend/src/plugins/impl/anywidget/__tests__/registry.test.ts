/* Copyright 2026 Marimo. All rights reserved. */
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  type MockInstance,
  vi,
} from "vitest";
import { getMarimoInternal, Model } from "../model";
import { handleWidgetMessage, WidgetRegistry } from "../registry";
import type { EsmSpec, ModelState, WidgetModelId } from "../types";
import { WIDGET_DEF_REGISTRY } from "../widget-binding";

// Helper to create typed model IDs for tests
const asModelId = (id: string): WidgetModelId => id as WidgetModelId;

// Mock the request client
const mockSendModelValue = vi.fn().mockResolvedValue(null);
vi.mock("@/core/network/requests", () => ({
  getRequestClient: () => ({
    sendModelValue: mockSendModelValue,
  }),
}));

// Mock isStaticNotebook — default to false (normal mode)
const mockIsStatic = vi.fn().mockReturnValue(false);
vi.mock("@/core/static/static-state", () => ({
  isStaticNotebook: () => mockIsStatic(),
}));

function createMockComm() {
  return {
    sendUpdate: vi.fn().mockResolvedValue(undefined),
    sendCustomMessage: vi.fn().mockResolvedValue(undefined),
  };
}

const SPEC: EsmSpec = { url: "./@file/10-widget.js", hash: "hash-1" };

describe("WidgetRegistry models", () => {
  let registry = new WidgetRegistry(50);
  const testId = asModelId("test-id");

  beforeEach(() => {
    registry = new WidgetRegistry(50);
    mockSendModelValue.mockClear();
  });

  it("should set and get models", async () => {
    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    registry.setModel(testId, model);
    const retrievedModel = await registry.getModel(testId);
    expect(retrievedModel).toBe(model);
  });

  it("should handle model not found", async () => {
    await expect(registry.getModel(asModelId("non-existent"))).rejects.toThrow(
      "Model not found for key: non-existent",
    );
  });

  it("accepts a fresh model after an earlier rendezvous times out", async () => {
    const id = asModelId("late-model");
    await expect(registry.getModel(id)).rejects.toThrow(
      "Model not found for key: late-model",
    );

    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    registry.setModel(id, model);

    await expect(registry.getModel(id)).resolves.toBe(model);
  });

  it("disposes a pre-open view when model rendezvous times out", async () => {
    const id = asModelId("timed-out-view");
    const host = document.createElement("div");
    const root = host.attachShadow({ mode: "open" });
    const el = document.createElement("div");
    root.append(el);
    const controller = new AbortController();

    const pending = registry.createView({
      modelId: id,
      el,
      signal: controller.signal,
    });
    expect(root.querySelector("style")).not.toBeNull();

    await expect(pending).rejects.toThrow(
      "Model not found for key: timed-out-view",
    );
    expect(root.querySelector("style")).toBeNull();
    expect(controller.signal.aborted).toBe(false);
  });

  it("should delete models", async () => {
    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    registry.setModel(testId, model);
    registry.delete(testId);
    await expect(registry.getModel(testId)).rejects.toThrow();
  });

  it("should handle widget messages", async () => {
    await handleWidgetMessage(registry, {
      model_id: testId,
      message: {
        method: "open",
        state: { count: 0 },
        buffer_paths: [],
        buffers: [],
      },
    });
    const model = await registry.getModel(testId);
    expect(model.get("count")).toBe(0);

    await handleWidgetMessage(registry, {
      model_id: testId,
      message: {
        method: "update",
        state: { count: 1 },
        buffer_paths: [],
        buffers: [],
      },
    });
    expect(model.get("count")).toBe(1);
  });

  it("should handle custom messages", async () => {
    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    const callback = vi.fn();
    model.on("msg:custom", callback);
    registry.setModel(testId, model);

    await handleWidgetMessage(registry, {
      model_id: testId,
      message: { method: "custom", content: { count: 1 }, buffers: [] },
    });
    expect(callback).toHaveBeenCalledWith({ count: 1 }, []);
  });

  it("should handle close messages", async () => {
    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    registry.setModel(testId, model);

    await handleWidgetMessage(registry, {
      model_id: testId,
      message: { method: "close" },
    });
    await expect(registry.getModel(testId)).rejects.toThrow();
  });

  describe("static mode", () => {
    beforeEach(() => {
      mockIsStatic.mockReturnValue(true);
    });

    afterEach(() => {
      mockIsStatic.mockReturnValue(false);
    });

    it("should create model with no-op comm in static mode", async () => {
      await handleWidgetMessage(registry, {
        model_id: testId,
        message: {
          method: "open",
          state: { count: 42 },
          buffer_paths: [],
          buffers: [],
        },
      });

      const model = await registry.getModel(testId);
      expect(model.get("count")).toBe(42);

      // save_changes should not call the real request client
      model.set("count", 100);
      model.save_changes();
      expect(mockSendModelValue).not.toHaveBeenCalled();
    });

    it("should not throw on send in static mode", async () => {
      await handleWidgetMessage(registry, {
        model_id: testId,
        message: {
          method: "open",
          state: { count: 0 },
          buffer_paths: [],
          buffers: [],
        },
      });

      const model = await registry.getModel(testId);
      // send() should silently no-op
      await expect(model.send({ test: true })).resolves.toBeUndefined();
      expect(mockSendModelValue).not.toHaveBeenCalled();
    });
  });
});

describe("WidgetRegistry.getWidget", () => {
  let registry = new WidgetRegistry(50);
  const testId = asModelId("widget-id");
  let getModuleSpy: MockInstance<typeof WIDGET_DEF_REGISTRY.getModule>;

  beforeEach(() => {
    registry = new WidgetRegistry(50);
    getModuleSpy = vi.spyOn(WIDGET_DEF_REGISTRY, "getModule");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("binds an undisplayed widget from its ESM spec", async () => {
    // The composition case: the child's model and spec arrived on its
    // open message, but no display mount ever renders it standalone.
    // getWidget must self-serve from the spec.
    const exports = { hello: vi.fn() };
    const widgetDef = {
      initialize: vi.fn().mockResolvedValue(exports),
      render: vi.fn(),
    };
    getModuleSpy.mockResolvedValue({ default: widgetDef });

    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    registry.setModel(testId, model);
    registry.setSpec(testId, SPEC);

    const widget = await registry.getWidget(testId);

    expect(getModuleSpy).toHaveBeenCalledWith({
      jsUrl: SPEC.url,
      jsHash: SPEC.hash,
      kernelAuthored: true,
    });
    expect(widgetDef.initialize).toHaveBeenCalledTimes(1);
    expect(widget.exports).toBe(exports);
  });

  it("records the spec from an open message", async () => {
    const widgetDef = { initialize: vi.fn(), render: vi.fn() };
    getModuleSpy.mockResolvedValue({ default: widgetDef });

    await handleWidgetMessage(registry, {
      model_id: testId,
      message: {
        method: "open",
        state: { count: 0 },
        buffer_paths: [],
        buffers: [],
        esm_spec: { url: SPEC.url, hash: SPEC.hash },
      },
    });

    await registry.getWidget(testId);
    expect(getModuleSpy).toHaveBeenCalledWith({
      jsUrl: SPEC.url,
      jsHash: SPEC.hash,
      kernelAuthored: true,
    });
  });

  it("shares one generation across concurrent and repeat callers", async () => {
    const widgetDef = { initialize: vi.fn(), render: vi.fn() };
    getModuleSpy.mockResolvedValue({ default: widgetDef });

    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    registry.setModel(testId, model);
    registry.setSpec(testId, SPEC);

    const [a, b] = await Promise.all([
      registry.getWidget(testId),
      registry.getWidget(testId),
    ]);
    const c = await registry.getWidget(testId);
    expect(a.exports).toBe(b.exports);
    expect(a.exports).toBe(c.exports);
    expect(widgetDef.initialize).toHaveBeenCalledTimes(1);
    expect(getModuleSpy).toHaveBeenCalledTimes(1);
  });

  it("fails fast for a model with no ESM spec", async () => {
    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    registry.setModel(testId, model);

    await expect(registry.getWidget(testId)).rejects.toThrow(
      /No ESM spec for model/,
    );
  });

  it("rejects when the module import fails, then retries fresh", async () => {
    getModuleSpy.mockRejectedValueOnce(new Error("network down"));

    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    registry.setModel(testId, model);
    registry.setSpec(testId, SPEC);

    await expect(registry.getWidget(testId)).rejects.toThrow("network down");

    // A failed generation must not poison the entry: the next call
    // starts over from the spec.
    const widgetDef = { initialize: vi.fn(), render: vi.fn() };
    getModuleSpy.mockResolvedValue({ default: widgetDef });
    const widget = await registry.getWidget(testId);
    expect(widget.exports).toBeUndefined();
    expect(widgetDef.initialize).toHaveBeenCalledTimes(1);
  });

  it("rejects with the AFM error when the module has no usable exports", async () => {
    const invalidateSpy = vi.spyOn(WIDGET_DEF_REGISTRY, "invalidate");
    getModuleSpy.mockResolvedValue({ notAWidget: true });

    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    registry.setModel(testId, model);
    registry.setSpec(testId, SPEC);

    await expect(registry.getWidget(testId)).rejects.toThrow(
      /missing a default export/,
    );
    expect(invalidateSpy).toHaveBeenCalledWith(SPEC.hash);
  });

  it("rejects when the model never arrives", async () => {
    await expect(registry.getWidget(asModelId("never-opened"))).rejects.toThrow(
      "Model not found for key: never-opened",
    );
  });

  it("rejects an in-flight initialize when the entry is deleted", async () => {
    const widgetDef = {
      initialize: vi.fn().mockReturnValue(new Promise(() => undefined)),
      render: vi.fn(),
    };
    getModuleSpy.mockResolvedValue({ default: widgetDef });

    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    registry.setModel(testId, model);
    registry.setSpec(testId, SPEC);

    const pending = registry.getWidget(testId);
    pending.catch(() => undefined);
    // Let the import resolve and initialize start.
    await new Promise((r) => setTimeout(r, 0));

    registry.delete(testId);
    await expect(pending).rejects.toThrow(/binding destroyed/);
  });

  it("destroys the generation on a close message", async () => {
    const initCleanup = vi.fn();
    const widgetDef = {
      initialize: vi.fn().mockResolvedValue(initCleanup),
      render: vi.fn(),
    };
    getModuleSpy.mockResolvedValue({ default: widgetDef });

    const model = new Model<ModelState>({ count: 0 }, createMockComm());
    registry.setModel(testId, model);
    registry.setSpec(testId, SPEC);
    await registry.getWidget(testId);

    await handleWidgetMessage(registry, {
      model_id: testId,
      message: { method: "close" },
    });
    expect(initCleanup).toHaveBeenCalledTimes(1);
  });
});

describe("WidgetRegistry generation swap (hot reload)", () => {
  const testId = asModelId("hmr-id");
  const SPEC_V1: EsmSpec = { url: "./@file/10-v1.js", hash: "hash-v1" };
  const SPEC_V2: EsmSpec = { url: "./@file/10-v2.js", hash: "hash-v2" };
  let getModuleSpy: MockInstance<typeof WIDGET_DEF_REGISTRY.getModule>;

  const makeWidget = (label: string) => ({
    initialize: vi.fn(),
    render: vi.fn(({ el }: { el: HTMLElement }) => {
      el.textContent = label;
    }),
  });

  beforeEach(() => {
    getModuleSpy = vi.spyOn(WIDGET_DEF_REGISTRY, "getModule");
  });

  afterEach(() => {
    getModuleSpy.mockRestore();
  });

  async function setup(isEditMode: boolean) {
    const registry = new WidgetRegistry(50, () => isEditMode);
    const v1 = makeWidget("v1");
    const v2 = makeWidget("v2");
    getModuleSpy.mockImplementation(async ({ jsUrl }) => {
      return jsUrl === SPEC_V1.url ? { default: v1 } : { default: v2 };
    });

    await handleWidgetMessage(registry, {
      model_id: testId,
      message: {
        method: "open",
        state: { count: 3 },
        buffer_paths: [],
        buffers: [],
        esm_spec: { url: SPEC_V1.url, hash: SPEC_V1.hash },
      },
    });
    const model = await registry.getModel(testId);
    const widget = await registry.getWidget(testId);

    // Mount a live view the swap must re-render.
    const el = document.createElement("div");
    const viewController = new AbortController();
    await widget.render({ el, signal: viewController.signal });
    expect(el.textContent).toBe("v1");

    return { registry, model, widget, el, viewController, v1, v2 };
  }

  it("preserves the initial spec before first mount outside edit mode", async () => {
    const registry = new WidgetRegistry(50, () => false);
    const v1 = makeWidget("v1");
    const v2 = makeWidget("v2");
    getModuleSpy.mockImplementation(async ({ jsUrl }) => ({
      default: jsUrl === SPEC_V1.url ? v1 : v2,
    }));
    registry.setModel(
      testId,
      new Model<ModelState>({ count: 0 }, createMockComm()),
    );
    registry.setSpec(testId, SPEC_V1);

    // A viewer may receive an editor's hot-reload update before it ever
    // mounts this widget. Its code must still be immutable for the model.
    registry.setSpec(testId, SPEC_V2);
    const widget = await registry.getWidget(testId);
    const el = document.createElement("div");
    await widget.render({ el });

    expect(el.textContent).toBe("v1");
    expect(v1.initialize).toHaveBeenCalledTimes(1);
    expect(v2.initialize).not.toHaveBeenCalled();
  });

  it("swaps the generation and re-renders live views in edit mode", async () => {
    const { registry, model, el, v1, v2 } = await setup(true);

    const onCount = vi.fn();
    model.on("change:count", onCount);

    await handleWidgetMessage(registry, {
      model_id: testId,
      message: {
        method: "update",
        state: {},
        buffer_paths: [],
        buffers: [],
        esm_spec: { url: SPEC_V2.url, hash: SPEC_V2.hash },
      },
    });

    const next = await registry.getWidget(testId);
    // Wait for the swap's re-render to land in the DOM.
    await vi.waitFor(() => {
      expect(el.textContent).toBe("v2");
    });
    expect(v2.initialize).toHaveBeenCalledTimes(1);
    expect(v2.render).toHaveBeenCalledTimes(1);
    // The old generation rendered exactly once, before the swap.
    expect(v1.render).toHaveBeenCalledTimes(1);
    // Model state persists across generations — that's the "hot" part.
    expect(next.exports).toBeUndefined();
    expect(model.get("count")).toBe(3);
    // Listeners registered outside the binding survive.
    model.set("count", 4);
    expect(onCount).toHaveBeenCalledTimes(1);
  });

  it("ignores replacement specs outside edit mode", async () => {
    const { registry, el, v2 } = await setup(false);

    await handleWidgetMessage(registry, {
      model_id: testId,
      message: {
        method: "update",
        state: {},
        buffer_paths: [],
        buffers: [],
        esm_spec: { url: SPEC_V2.url, hash: SPEC_V2.hash },
      },
    });

    await registry.getWidget(testId);
    expect(v2.initialize).not.toHaveBeenCalled();
    expect(el.textContent).toBe("v1");
  });

  it("ignores an update whose spec hash is unchanged", async () => {
    const { registry, v1 } = await setup(true);

    await handleWidgetMessage(registry, {
      model_id: testId,
      message: {
        method: "update",
        state: {},
        buffer_paths: [],
        buffers: [],
        esm_spec: { url: SPEC_V1.url, hash: SPEC_V1.hash },
      },
    });

    await registry.getWidget(testId);
    expect(v1.initialize).toHaveBeenCalledTimes(1);
  });

  it("cleans up the old generation's listeners on swap", async () => {
    const { registry, model } = await setup(true);

    // v1's render registered nothing; attach a listener the way a
    // widget would, through a generation-scoped proxy — easiest to
    // observe via initialize cleanup of a fresh generation:
    const onCount = vi.fn();
    const v3 = {
      initialize: vi.fn(({ model }: { model: { on: Function } }) => {
        model.on("change:count", onCount);
      }),
      render: vi.fn(),
    };
    getModuleSpy.mockResolvedValue({ default: v3 });

    await handleWidgetMessage(registry, {
      model_id: testId,
      message: {
        method: "update",
        state: {},
        buffer_paths: [],
        buffers: [],
        esm_spec: { url: "./@file/10-v3.js", hash: "hash-v3" },
      },
    });
    await registry.getWidget(testId);

    model.set("count", 10);
    expect(onCount).toHaveBeenCalledTimes(1);

    // Swap again: v3's listener must be gone afterwards.
    getModuleSpy.mockResolvedValue({ default: makeWidget("v4") });
    await handleWidgetMessage(registry, {
      model_id: testId,
      message: {
        method: "update",
        state: {},
        buffer_paths: [],
        buffers: [],
        esm_spec: { url: "./@file/10-v4.js", hash: "hash-v4" },
      },
    });
    await registry.getWidget(testId);

    model.set("count", 11);
    expect(onCount).toHaveBeenCalledTimes(1);
  });

  it("starts a new generation without waiting for stale initialize", async () => {
    const registry = new WidgetRegistry(50, () => true);
    const first = {
      initialize: vi.fn().mockReturnValue(new Promise(() => undefined)),
      render: vi.fn(),
    };
    const second = { initialize: vi.fn(), render: vi.fn() };
    getModuleSpy.mockImplementation(async ({ jsUrl }) => ({
      default: jsUrl === SPEC_V1.url ? first : second,
    }));
    registry.setModel(
      testId,
      new Model<ModelState>({ count: 0 }, createMockComm()),
    );
    registry.setSpec(testId, SPEC_V1);

    const waiting = registry.getWidget(testId);
    await new Promise((resolve) => setTimeout(resolve, 0));
    registry.setSpec(testId, SPEC_V2);

    await expect(waiting).resolves.toBeDefined();
    expect(second.initialize).toHaveBeenCalledTimes(1);
  });

  it("waits for old render cleanup before rendering the replacement", async () => {
    const registry = new WidgetRegistry(50, () => true);
    let cleanupStarted!: () => void;
    const started = new Promise<void>((resolve) => {
      cleanupStarted = resolve;
    });
    let finishCleanup!: () => void;
    const cleanupGate = new Promise<void>((resolve) => {
      finishCleanup = resolve;
    });
    const v1 = {
      initialize: vi.fn(),
      render: vi.fn(({ el }: { el: HTMLElement }) => {
        el.textContent = "v1";
        return async () => {
          cleanupStarted();
          await cleanupGate;
          el.textContent = "stale cleanup";
        };
      }),
    };
    const v2 = makeWidget("v2");
    getModuleSpy.mockImplementation(async ({ jsUrl }) => ({
      default: jsUrl === SPEC_V1.url ? v1 : v2,
    }));
    registry.setModel(
      testId,
      new Model<ModelState>({ count: 0 }, createMockComm()),
    );
    registry.setSpec(testId, SPEC_V1);
    const widget = await registry.getWidget(testId);
    const el = document.createElement("div");
    await widget.render({ el });

    registry.setSpec(testId, SPEC_V2);
    await started;
    await new Promise((resolve) => setTimeout(resolve, 0));
    const rendersBeforeCleanupFinished = v2.render.mock.calls.length;

    finishCleanup();
    expect(rendersBeforeCleanupFinished).toBe(0);
    await vi.waitFor(() => {
      expect(el.textContent).toBe("v2");
    });
    expect(v2.render).toHaveBeenCalledTimes(1);
  });
});

describe("WidgetRegistry runtime styles", () => {
  it("mounts composed widget CSS in its render root", async () => {
    const registry = new WidgetRegistry(50);
    const id = asModelId("styled-child");
    const getModuleSpy = vi
      .spyOn(WIDGET_DEF_REGISTRY, "getModule")
      .mockResolvedValue({ default: { render: vi.fn() } });
    const model = new Model<ModelState>(
      { _css: ".child { color: red; }" },
      createMockComm(),
    );
    registry.setModel(id, model);
    registry.setSpec(id, {
      url: "./@file/styled-child.js",
      hash: "styled-child-hash",
    });
    const host = document.createElement("div");
    const root = host.attachShadow({ mode: "open" });
    const el = document.createElement("div");
    root.append(el);
    const controller = new AbortController();

    try {
      await registry.createView({
        modelId: id,
        el,
        signal: controller.signal,
      });
      expect(root.querySelector("style")?.textContent).toContain("color: red");

      model.set("_css", ".child { color: blue; }");
      expect(root.querySelector("style")?.textContent).toContain("color: blue");

      controller.abort();
      expect(root.querySelector("style")).toBeNull();
    } finally {
      registry.delete(id);
      getModuleSpy.mockRestore();
    }
  });
});

describe("WidgetRegistry custom messages during rendezvous", () => {
  it("emits custom messages arriving before getWidget resolves", async () => {
    // Regression guard for the rendezvous ordering: state and custom
    // messages must flow to a model even while a generation is pending.
    const registry = new WidgetRegistry(50);
    const testId = asModelId("pending-custom");
    const widgetDef = { initialize: vi.fn(), render: vi.fn() };
    const getModuleSpy = vi
      .spyOn(WIDGET_DEF_REGISTRY, "getModule")
      .mockResolvedValue({ default: widgetDef });

    try {
      const model = new Model<ModelState>({ count: 0 }, createMockComm());
      const callback = vi.fn();
      model.on("msg:custom", callback);
      registry.setModel(testId, model);
      registry.setSpec(testId, SPEC);

      const pending = registry.getWidget(testId);
      getMarimoInternal(model).emitCustomMessage({
        method: "custom",
        content: { ping: 1 },
      });
      await pending;
      expect(callback).toHaveBeenCalledWith({ ping: 1 }, []);
    } finally {
      getModuleSpy.mockRestore();
    }
  });
});
