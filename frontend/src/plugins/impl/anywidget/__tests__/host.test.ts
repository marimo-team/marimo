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
import { createHost } from "../host";
import { Model } from "../model";
import { WIDGET_REGISTRY } from "../registry";
import type { ModelState, WidgetModelId } from "../types";
import { visibleForTesting, WIDGET_DEF_REGISTRY } from "../widget-binding";
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
  // Each test uses a unique model id so global WIDGET_REGISTRY state
  // from earlier tests doesn't leak in.
  let nextId = 0;
  let modelId: WidgetModelId;
  let parentController: AbortController;
  let getModuleSpy: MockInstance<typeof WIDGET_DEF_REGISTRY.getModule>;

  beforeEach(() => {
    nextId += 1;
    modelId = asModelId(`host-test-${nextId}`);
    parentController = new AbortController();
    getModuleSpy = vi.spyOn(WIDGET_DEF_REGISTRY, "getModule");
  });

  afterEach(() => {
    WIDGET_REGISTRY.delete(modelId);
    getModuleSpy.mockRestore();
  });

  /** Register a child in the global registry the way an open message
   * would: model + ESM spec, with the module load answered by the spy. */
  function registerChild(
    widgetDef: object,
    state?: ModelState,
  ): Model<ModelState> {
    const childModel = new Model<ModelState>(
      state ?? { count: 0 },
      createMockComm(),
    );
    WIDGET_REGISTRY.setModel(modelId, childModel);
    WIDGET_REGISTRY.setSpec(modelId, {
      url: `./@file/10-${modelId}.js`,
      // Unique per test: the def registry caches modules by hash.
      hash: `hash-${modelId}`,
    });
    getModuleSpy.mockResolvedValue({ default: widgetDef });
    return childModel;
  }

  describe("getModel", () => {
    it("resolves the child model by ref", async () => {
      const childModel = new Model<ModelState>({ value: 42 }, createMockComm());
      WIDGET_REGISTRY.setModel(modelId, childModel);

      const host = createHost(WIDGET_REGISTRY, parentController.signal);
      const resolved = await host.getModel(ref(modelId));
      expect(resolved.get("value")).toBe(42);
    });

    it("rejects an invalid ref", async () => {
      const host = createHost(WIDGET_REGISTRY, parentController.signal);
      await expect(host.getModel("IPY_MODEL_xyz")).rejects.toThrow(/Invalid/);
    });

    it("scopes listeners on the resolved model to the parent's signal", async () => {
      const childModel = new Model<ModelState>({ count: 0 }, createMockComm());
      WIDGET_REGISTRY.setModel(modelId, childModel);

      const host = createHost(WIDGET_REGISTRY, parentController.signal);
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
    it("resolves an undisplayed child with exports and a render method", async () => {
      const exports = { setValue: vi.fn() };
      const widgetDef = {
        initialize: vi.fn().mockResolvedValue(exports),
        render: vi.fn(),
      };
      registerChild(widgetDef);

      const host = createHost(WIDGET_REGISTRY, parentController.signal);
      const resolved = await host.getWidget(ref(modelId));
      expect(resolved.exports).toBe(exports);

      const el = document.createElement("div");
      await resolved.render({ el });
      expect(widgetDef.render).toHaveBeenCalledTimes(1);
      expect(widgetDef.render.mock.calls[0][0].el).toBe(el);
    });

    it("waits for an in-flight `initialize` to settle", async () => {
      let resolveInit!: (v: object) => void;
      const widgetDef = {
        initialize: vi.fn().mockReturnValue(
          new Promise<object>((r) => {
            resolveInit = r;
          }),
        ),
        render: vi.fn(),
      };
      registerChild(widgetDef);

      const host = createHost(WIDGET_REGISTRY, parentController.signal);
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

    it("rejects if the child is deleted mid-initialize", async () => {
      const widgetDef = {
        initialize: vi.fn().mockReturnValue(new Promise(() => undefined)),
        render: vi.fn(),
      };
      registerChild(widgetDef);

      const host = createHost(WIDGET_REGISTRY, parentController.signal);
      const widgetPromise = host.getWidget(ref(modelId));
      widgetPromise.catch(() => undefined);
      // Let the import resolve and initialize start.
      await new Promise((r) => setTimeout(r, 0));

      WIDGET_REGISTRY.delete(modelId);

      await expect(widgetPromise).rejects.toThrow(/binding destroyed/);
    });

    it("rejects for a child that has no ESM spec", async () => {
      // e.g. a ref to a traditional jupyter widget's model.
      const childModel = new Model<ModelState>({ count: 0 }, createMockComm());
      WIDGET_REGISTRY.setModel(modelId, childModel);

      const host = createHost(WIDGET_REGISTRY, parentController.signal);
      await expect(host.getWidget(ref(modelId))).rejects.toThrow(/No ESM spec/);
    });

    it("uses the parent's signal as a default for child render", async () => {
      const widgetDef = {
        initialize: vi.fn(),
        render: vi.fn(),
      };
      registerChild(widgetDef);

      const host = createHost(WIDGET_REGISTRY, parentController.signal);
      const resolved = await host.getWidget(ref(modelId));

      await resolved.render({ el: document.createElement("div") });
      const childRenderSignal = widgetDef.render.mock.calls[0][0].signal;
      expect(childRenderSignal.aborted).toBe(false);

      // Aborting the parent signal cascades to the child's view.
      parentController.abort();
      expect(childRenderSignal.aborted).toBe(true);
    });

    it("uses the caller-supplied signal when given, ignoring the parent default", async () => {
      const widgetDef = {
        initialize: vi.fn(),
        render: vi.fn(),
      };
      registerChild(widgetDef);

      const host = createHost(WIDGET_REGISTRY, parentController.signal);
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
    const getModuleSpy = vi.spyOn(WIDGET_DEF_REGISTRY, "getModule");
    try {
      const childExports = { id: "child" };
      const childWidget = {
        initialize: vi.fn().mockResolvedValue(childExports),
        render: vi.fn(),
      };
      const childModel = new Model<ModelState>({ count: 0 }, createMockComm());
      WIDGET_REGISTRY.setModel(childId, childModel);
      WIDGET_REGISTRY.setSpec(childId, {
        url: "./@file/10-host-render-child.js",
        hash: "hash-host-render-child",
      });
      getModuleSpy.mockResolvedValue({ default: childWidget });

      const parentModel = new Model<ModelState>(
        { child: `${WIDGET_REF_PREFIX}${childId}` },
        createMockComm(),
      );
      WIDGET_REGISTRY.setModel(parentId, parentModel);

      const parentWidget = {
        initialize: vi.fn(),
        render: vi.fn(),
      };
      const parentBinding = await WidgetBinding.create({
        widgetDef: parentWidget,
        model: parentModel,
        createHost: (signal) => createHost(WIDGET_REGISTRY, signal),
      });

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
      WIDGET_REGISTRY.delete(parentId);
      WIDGET_REGISTRY.delete(childId);
      getModuleSpy.mockRestore();
    }
  });
});

describe("host-mounted views", () => {
  it("render with the child's current model state", async () => {
    const childId = asModelId("host-child-state");
    const parentController = new AbortController();
    const getModuleSpy = vi.spyOn(WIDGET_DEF_REGISTRY, "getModule");
    try {
      const childWidget = {
        render: vi.fn(({ model, el }) => {
          el.textContent = `count is ${model.get("count")}`;
        }),
      };
      const childModel = new Model<ModelState>({ count: 8 }, createMockComm());
      WIDGET_REGISTRY.setModel(childId, childModel);
      WIDGET_REGISTRY.setSpec(childId, {
        url: "./@file/10-host-child-state.js",
        hash: "hash-host-child-state",
      });
      getModuleSpy.mockResolvedValue({ default: childWidget });

      const host = createHost(WIDGET_REGISTRY, parentController.signal);
      const resolved = await host.getWidget(ref(childId));

      const el = document.createElement("div");
      await resolved.render({ el });
      expect(el.textContent).toBe("count is 8");
    } finally {
      WIDGET_REGISTRY.delete(childId);
      getModuleSpy.mockRestore();
    }
  });
});
