/* Copyright 2026 Marimo. All rights reserved. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createHost } from "../host";
import { MODEL_MANAGER, Model } from "../model";
import type { ModelState, WidgetModelId } from "../types";
import { BINDING_MANAGER, visibleForTesting } from "../widget-binding";
import { WIDGET_REF_PREFIX } from "../widget-ref";

const { WidgetBinding } = visibleForTesting;

const asModelId = (id: string): WidgetModelId => id as WidgetModelId;
const ref = (id: string): string => `${WIDGET_REF_PREFIX}${id}`;

function createMockComm() {
  return {
    sendUpdate: vi.fn().mockResolvedValue(undefined),
    sendCustomMessage: vi.fn().mockResolvedValue(undefined),
  };
}

describe("createHost", () => {
  // Each test uses a unique model id so the global MODEL_MANAGER /
  // BINDING_MANAGER state from earlier tests doesn't leak in.
  let nextId = 0;
  let modelId: WidgetModelId;
  let parentController: AbortController;

  beforeEach(() => {
    nextId += 1;
    modelId = asModelId(`host-test-${nextId}`);
    parentController = new AbortController();
  });

  afterEach(() => {
    BINDING_MANAGER.destroy(modelId);
    MODEL_MANAGER.delete(modelId);
  });

  describe("getModel", () => {
    it("resolves the child model by ref", async () => {
      const childModel = new Model<ModelState>({ value: 42 }, createMockComm());
      MODEL_MANAGER.set(modelId, childModel);

      const host = createHost(parentController.signal);
      const resolved = await host.getModel(ref(modelId));
      expect(resolved.get("value")).toBe(42);
    });

    it("rejects an invalid ref", async () => {
      const host = createHost(parentController.signal);
      await expect(host.getModel("IPY_MODEL_xyz")).rejects.toThrow(/Invalid/);
    });

    it("scopes listeners on the resolved model to the parent's signal", async () => {
      const childModel = new Model<ModelState>({ count: 0 }, createMockComm());
      MODEL_MANAGER.set(modelId, childModel);

      const host = createHost(parentController.signal);
      const resolved = await host.getModel(ref(modelId));

      const cb = vi.fn();
      resolved.on("change:count", cb);
      childModel.set("count", 1);
      expect(cb).toHaveBeenCalledTimes(1);

      // Aborting the parent signal should clear the listener even though
      // the caller never wired it up themselves.
      parentController.abort();
      childModel.set("count", 2);
      expect(cb).toHaveBeenCalledTimes(1);
    });
  });

  describe("getWidget", () => {
    it("resolves with the child's exports and a render method", async () => {
      const childModel = new Model<ModelState>({ count: 0 }, createMockComm());
      MODEL_MANAGER.set(modelId, childModel);

      const exports = { setValue: vi.fn() };
      const widgetDef = {
        initialize: vi.fn().mockResolvedValue(exports),
        render: vi.fn(),
      };

      const binding = BINDING_MANAGER.getOrCreate(modelId);
      await binding.bind(widgetDef, childModel);

      const host = createHost(parentController.signal);
      const resolved = await host.getWidget(ref(modelId));
      expect(resolved.exports).toBe(exports);

      const el = document.createElement("div");
      await resolved.render({ el });
      expect(widgetDef.render).toHaveBeenCalledTimes(1);
      expect(widgetDef.render.mock.calls[0][0].el).toBe(el);
    });

    it("waits for an in-flight `initialize` to settle", async () => {
      const childModel = new Model<ModelState>({ count: 0 }, createMockComm());
      MODEL_MANAGER.set(modelId, childModel);

      let resolveInit!: (v: object) => void;
      const widgetDef = {
        initialize: vi.fn().mockReturnValue(
          new Promise<object>((r) => {
            resolveInit = r;
          }),
        ),
        render: vi.fn(),
      };

      const binding = BINDING_MANAGER.getOrCreate(modelId);
      void binding.bind(widgetDef, childModel);

      const host = createHost(parentController.signal);
      const widgetPromise = host.getWidget(ref(modelId));

      // Until initialize resolves, getWidget should be pending.
      let resolvedExports: unknown;
      widgetPromise.then((w) => {
        resolvedExports = w.exports;
      });
      await new Promise((r) => setTimeout(r, 5));
      expect(resolvedExports).toBeUndefined();

      const exports = { ready: true };
      resolveInit(exports);
      const resolved = await widgetPromise;
      expect(resolved.exports).toBe(exports);
    });

    it("rejects if the child binding is destroyed mid-initialize", async () => {
      const childModel = new Model<ModelState>({ count: 0 }, createMockComm());
      MODEL_MANAGER.set(modelId, childModel);

      const widgetDef = {
        initialize: vi.fn().mockReturnValue(new Promise(() => undefined)),
        render: vi.fn(),
      };

      const binding = BINDING_MANAGER.getOrCreate(modelId);
      void binding.bind(widgetDef, childModel);

      const host = createHost(parentController.signal);
      const widgetPromise = host.getWidget(ref(modelId));
      widgetPromise.catch(() => undefined);

      binding.destroy();

      await expect(widgetPromise).rejects.toThrow(/binding destroyed/);
    });

    it("uses the parent's signal as a default for child render", async () => {
      const childModel = new Model<ModelState>({ count: 0 }, createMockComm());
      MODEL_MANAGER.set(modelId, childModel);

      const widgetDef = {
        initialize: vi.fn(),
        render: vi.fn(),
      };

      const binding = BINDING_MANAGER.getOrCreate(modelId);
      await binding.bind(widgetDef, childModel);

      const host = createHost(parentController.signal);
      const resolved = await host.getWidget(ref(modelId));

      await resolved.render({ el: document.createElement("div") });
      const childRenderSignal = widgetDef.render.mock.calls[0][0].signal;
      expect(childRenderSignal.aborted).toBe(false);

      // Aborting the parent signal cascades to the child's view.
      parentController.abort();
      expect(childRenderSignal.aborted).toBe(true);
    });

    it("uses the caller-supplied signal when given, ignoring the parent default", async () => {
      const childModel = new Model<ModelState>({ count: 0 }, createMockComm());
      MODEL_MANAGER.set(modelId, childModel);

      const widgetDef = {
        initialize: vi.fn(),
        render: vi.fn(),
      };

      const binding = BINDING_MANAGER.getOrCreate(modelId);
      await binding.bind(widgetDef, childModel);

      const host = createHost(parentController.signal);
      const resolved = await host.getWidget(ref(modelId));

      const childController = new AbortController();
      await resolved.render({
        el: document.createElement("div"),
        signal: childController.signal,
      });
      const childRenderSignal = widgetDef.render.mock.calls[0][0].signal;
      expect(childRenderSignal.aborted).toBe(false);

      childController.abort();
      expect(childRenderSignal.aborted).toBe(true);
    });
  });
});

describe("WidgetBinding receives a host in render props", () => {
  it("passes a host into render whose getWidget resolves siblings", async () => {
    const parentId = asModelId("host-render-parent");
    const childId = asModelId("host-render-child");
    const parentController = new AbortController();
    try {
      const childModel = new Model<ModelState>({ count: 0 }, createMockComm());
      MODEL_MANAGER.set(childId, childModel);

      const childExports = { id: "child" };
      const childWidget = {
        initialize: vi.fn().mockResolvedValue(childExports),
        render: vi.fn(),
      };
      const childBinding = BINDING_MANAGER.getOrCreate(childId);
      await childBinding.bind(childWidget, childModel);

      const parentModel = new Model<ModelState>(
        { child: `${WIDGET_REF_PREFIX}${childId}` },
        createMockComm(),
      );
      MODEL_MANAGER.set(parentId, parentModel);

      const parentBinding = new WidgetBinding();
      const parentWidget = {
        initialize: vi.fn(),
        render: vi.fn(),
      };
      await parentBinding.bind(parentWidget, parentModel);

      await parentBinding.createView(
        { el: document.createElement("div") },
        { signal: parentController.signal },
      );

      const renderProps = parentWidget.render.mock.calls[0][0];
      expect(renderProps.host).toBeDefined();
      expect(typeof renderProps.host.getWidget).toBe("function");

      const resolved = await renderProps.host.getWidget(
        parentModel.get("child"),
      );
      expect(resolved.exports).toBe(childExports);
    } finally {
      BINDING_MANAGER.destroy(parentId);
      BINDING_MANAGER.destroy(childId);
      MODEL_MANAGER.delete(parentId);
      MODEL_MANAGER.delete(childId);
    }
  });
});
