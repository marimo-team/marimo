/* Copyright 2026 Marimo. All rights reserved. */
import {
  afterAll,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import { TestUtils } from "@/__tests__/test-helpers";
import {
  getMarimoInternal,
  handleWidgetMessage,
  Model,
  visibleForTesting,
} from "../model";
import type { WidgetModelId } from "../types";
import { BINDING_MANAGER } from "../widget-binding";

const { ModelManager } = visibleForTesting;

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

// Helper to create a mock MarimoComm
function createMockComm<T>() {
  return {
    sendUpdate: vi.fn().mockResolvedValue(undefined),
    sendCustomMessage: vi.fn().mockResolvedValue(undefined),
  };
}

describe("Model", () => {
  let model: Model<{ foo: string; bar: number }>;
  let mockComm: ReturnType<typeof createMockComm<{ foo: string; bar: number }>>;

  beforeEach(() => {
    mockComm = createMockComm();
    mockSendModelValue.mockClear();
    model = new Model({ foo: "test", bar: 123 }, mockComm);
  });

  describe("public API", () => {
    it("should only expose AFM-compliant interface", () => {
      // Get all enumerable own properties
      const ownProperties = Object.keys(model).sort();
      // Get prototype methods (excluding constructor)
      const prototypeMethods = Object.getOwnPropertyNames(
        Object.getPrototypeOf(model),
      )
        .filter((name) => name !== "constructor")
        .sort();

      // Snapshot the public API to catch accidental leaks of internal methods
      expect({ ownProperties, prototypeMethods }).toMatchInlineSnapshot(`
        {
          "ownProperties": [
            "widget_manager",
          ],
          "prototypeMethods": [
            "get",
            "off",
            "on",
            "save_changes",
            "send",
            "set",
          ],
        }
      `);
    });
  });

  describe("get/set", () => {
    it("should get values correctly", () => {
      expect(model.get("foo")).toBe("test");
      expect(model.get("bar")).toBe(123);
    });

    it("should set values and emit change events", () => {
      const callback = vi.fn();
      model.on("change:foo", callback);
      model.set("foo", "new value");

      expect(callback).toHaveBeenCalledWith("new value");
      expect(model.get("foo")).toBe("new value");
    });

    it("should not emit change events for non-subscribed fields", () => {
      const callback = vi.fn();
      model.on("change:foo", callback);
      model.set("bar", 456);

      expect(callback).not.toHaveBeenCalled();
    });
  });

  describe("save_changes", () => {
    it("should only save dirty fields", () => {
      model.set("foo", "new value");
      model.set("bar", 456);
      model.save_changes();

      expect(mockComm.sendUpdate).toHaveBeenCalledWith({
        foo: "new value",
        bar: 456,
      });
    });

    it("should clear dirty fields after save", () => {
      model.set("foo", "new value");
      model.save_changes();

      expect(mockComm.sendUpdate).toHaveBeenCalledWith({
        foo: "new value",
      });

      model.set("bar", 456);
      model.save_changes();

      // After clearing, only the newly changed field is sent
      expect(mockComm.sendUpdate).toHaveBeenCalledWith({
        bar: 456,
      });
    });

    it("should not call sendUpdate when no dirty fields", () => {
      model.set("foo", "new value");
      model.save_changes();
      model.save_changes(); // Second save should not call sendUpdate

      expect(mockComm.sendUpdate).toHaveBeenCalledTimes(1);
    });
  });

  describe("event handling", () => {
    it("should add and remove event listeners", () => {
      const callback = vi.fn();
      model.on("change:foo", callback);
      model.set("foo", "new value");
      expect(callback).toHaveBeenCalledTimes(1);

      model.off("change:foo", callback);
      model.set("foo", "another value");
      expect(callback).toHaveBeenCalledTimes(1);
    });

    it("should remove all listeners when no event name provided", () => {
      const callback1 = vi.fn();
      const callback2 = vi.fn();
      model.on("change:foo", callback1);
      model.on("change:bar", callback2);

      model.off();
      model.set("foo", "new value");
      model.set("bar", 456);

      expect(callback1).not.toHaveBeenCalled();
      expect(callback2).not.toHaveBeenCalled();
    });

    it("should remove all listeners for specific event", () => {
      const callback1 = vi.fn();
      const callback2 = vi.fn();
      model.on("change:foo", callback1);
      model.on("change:foo", callback2);

      model.off("change:foo");
      model.set("foo", "new value");

      expect(callback1).not.toHaveBeenCalled();
      expect(callback2).not.toHaveBeenCalled();
    });
  });

  describe("send", () => {
    it("should send message and handle callbacks", async () => {
      const callback = vi.fn();
      await model.send({ test: true }, callback);

      expect(mockComm.sendCustomMessage).toHaveBeenCalledWith(
        { test: true },
        [],
      );
      expect(callback).toHaveBeenCalled();
    });

    it("should convert buffers to DataViews", async () => {
      const buffer = new ArrayBuffer(8);
      await model.send({ test: true }, undefined, [buffer]);

      expect(mockComm.sendCustomMessage).toHaveBeenCalledWith({ test: true }, [
        expect.any(DataView),
      ]);
    });
  });

  describe("widget_manager", () => {
    const childModelId = asModelId("test-id");
    const childModel = new Model({ foo: "test" }, createMockComm());
    const manager = new ModelManager(10);
    let previousModelManager = Model._modelManager;

    beforeAll(() => {
      previousModelManager = Model._modelManager;
      manager.set(childModelId, childModel);
      Model._modelManager = manager;
    });

    afterAll(() => {
      manager.delete(childModelId);
      Model._modelManager = previousModelManager;
    });

    it("should throw error when accessing a model that is not registered", async () => {
      await expect(
        model.widget_manager.get_model(asModelId("random-id")),
      ).rejects.toThrow("Model not found for key: random-id");
    });

    it("should return the registered model", async () => {
      expect(await model.widget_manager.get_model(childModelId)).toBe(
        childModel,
      );
    });
  });

  describe("updateAndEmitDiffs", () => {
    it("should only update and emit for changed values", () => {
      const callback = vi.fn();
      model.on("change:foo", callback);

      getMarimoInternal(model).updateAndEmitDiffs({ foo: "test", bar: 456 });
      expect(callback).not.toHaveBeenCalled(); // foo didn't change
      expect(model.get("bar")).toBe(456);
    });

    it("should update and emit for deep changes", () => {
      const modelWithObject = new Model<{ foo: { nested: string } }>(
        { foo: { nested: "test" } },
        createMockComm(),
      );
      const callback = vi.fn();
      modelWithObject.on("change:foo", callback);

      getMarimoInternal(modelWithObject).updateAndEmitDiffs({
        foo: { nested: "changed" },
      });
      expect(callback).toHaveBeenCalledTimes(1);
    });

    it("should emit change event for any changes", async () => {
      const callback = vi.fn();
      model.on("change", callback);
      getMarimoInternal(model).updateAndEmitDiffs({ foo: "changed", bar: 456 });
      await TestUtils.nextTick(); // flush
      expect(callback).toHaveBeenCalledTimes(1);
    });
  });

  describe("emitCustomMessage", () => {
    it("should handle custom messages", () => {
      const callback = vi.fn();
      model.on("msg:custom", callback);

      const content = { type: "test" };
      getMarimoInternal(model).emitCustomMessage({
        method: "custom",
        content,
      });

      expect(callback).toHaveBeenCalledWith(content, []);
    });

    it("should handle custom messages with buffers", () => {
      const callback = vi.fn();
      model.on("msg:custom", callback);

      const content = { type: "test" };
      const buffer = new DataView(new ArrayBuffer(8));
      getMarimoInternal(model).emitCustomMessage(
        {
          method: "custom",
          content,
        },
        [buffer],
      );

      expect(callback).toHaveBeenCalledWith(content, [buffer]);
    });
  });
});

describe("ModelManager", () => {
  let modelManager = new ModelManager(50);
  const testId = asModelId("test-id");

  beforeEach(() => {
    // Clear the model manager before each test
    modelManager = new ModelManager(50);
    mockSendModelValue.mockClear();
  });

  it("should set and get models", async () => {
    const model = new Model({ count: 0 }, createMockComm());
    modelManager.set(testId, model);
    const retrievedModel = await modelManager.get(testId);
    expect(retrievedModel).toBe(model);
  });

  it("should handle model not found", async () => {
    await expect(modelManager.get(asModelId("non-existent"))).rejects.toThrow(
      "Model not found for key: non-existent",
    );
  });

  it("should delete models", async () => {
    const model = new Model({ count: 0 }, createMockComm());
    modelManager.set(testId, model);
    modelManager.delete(testId);
    await expect(modelManager.get(testId)).rejects.toThrow();
  });

  it("should handle widget messages", async () => {
    await handleWidgetMessage(modelManager, {
      model_id: testId,
      message: {
        method: "open",
        state: { count: 0 },
        buffer_paths: [],
        buffers: [],
      },
    });
    const model = await modelManager.get(testId);
    expect(model.get("count")).toBe(0);

    await handleWidgetMessage(modelManager, {
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
    const model = new Model({ count: 0 }, createMockComm());
    const callback = vi.fn();
    model.on("msg:custom", callback);
    modelManager.set(testId, model);

    await handleWidgetMessage(modelManager, {
      model_id: testId,
      message: { method: "custom", content: { count: 1 }, buffers: [] },
    });
    expect(callback).toHaveBeenCalledWith({ count: 1 }, []);
  });

  it("should handle close messages", async () => {
    const model = new Model({ count: 0 }, createMockComm());
    modelManager.set(testId, model);

    await handleWidgetMessage(modelManager, {
      model_id: testId,
      message: { method: "close" },
    });
    await expect(modelManager.get(testId)).rejects.toThrow();
  });

  it("should destroy binding on close message", async () => {
    const model = new Model({ count: 0 }, createMockComm());
    modelManager.set(testId, model);

    // Create a binding for this model
    BINDING_MANAGER.getOrCreate(testId);
    expect(BINDING_MANAGER.has(testId)).toBe(true);

    await handleWidgetMessage(modelManager, {
      model_id: testId,
      message: { method: "close" },
    });

    expect(BINDING_MANAGER.has(testId)).toBe(false);
  });

  describe("static mode", () => {
    beforeEach(() => {
      mockIsStatic.mockReturnValue(true);
    });

    afterAll(() => {
      mockIsStatic.mockReturnValue(false);
    });

    it("should create model with no-op comm in static mode", async () => {
      await handleWidgetMessage(modelManager, {
        model_id: testId,
        message: {
          method: "open",
          state: { count: 42 },
          buffer_paths: [],
          buffers: [],
        },
      });

      const model = await modelManager.get(testId);
      expect(model.get("count")).toBe(42);

      // save_changes should not call the real request client
      model.set("count", 100);
      model.save_changes();
      expect(mockSendModelValue).not.toHaveBeenCalled();
    });

    it("should not throw on send in static mode", async () => {
      await handleWidgetMessage(modelManager, {
        model_id: testId,
        message: {
          method: "open",
          state: { count: 0 },
          buffer_paths: [],
          buffers: [],
        },
      });

      const model = await modelManager.get(testId);
      // send() should silently no-op
      await expect(model.send({ test: true })).resolves.toBeUndefined();
      expect(mockSendModelValue).not.toHaveBeenCalled();
    });
  });
});
