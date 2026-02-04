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
  type AnyWidgetMessage,
  handleWidgetMessage,
  Model,
  visibleForTesting,
} from "../model";
import type { WidgetModelId } from "../types";

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

describe("Model", () => {
  let model: Model<{ foo: string; bar: number }>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let onChange: (value: any) => void;
  const modelId = asModelId("test-model-id");

  beforeEach(() => {
    onChange = vi.fn();
    mockSendModelValue.mockClear();
    model = new Model({ foo: "test", bar: 123 }, onChange, modelId);
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

      expect(onChange).toHaveBeenCalledWith({
        foo: "new value",
        bar: 456,
      });
    });

    it("should clear dirty fields after save", () => {
      model.set("foo", "new value");
      model.save_changes();

      expect(onChange).toHaveBeenCalledWith({
        foo: "new value",
      });

      model.set("bar", 456);
      model.save_changes();

      // After clearing, only the newly changed field is sent
      expect(onChange).toHaveBeenCalledWith({
        bar: 456,
      });
    });

    it("should not call onChange when no dirty fields", () => {
      model.set("foo", "new value");
      model.save_changes();
      model.save_changes(); // Second save should not call onChange

      expect(onChange).toHaveBeenCalledTimes(1);
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
      model.send({ test: true }, callback);

      expect(mockSendModelValue).toHaveBeenCalledWith({
        modelId: modelId,
        message: {
          state: { test: true },
          bufferPaths: [],
          method: "custom",
          content: { test: true },
        },
        buffers: [],
      });
      await TestUtils.nextTick(); // flush
      expect(callback).toHaveBeenCalledWith(null);
    });
  });

  describe("widget_manager", () => {
    const childModelId = asModelId("test-id");
    const childModel = new Model({ foo: "test" }, vi.fn(), childModelId);
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

      model.updateAndEmitDiffs({ foo: "test", bar: 456 });
      expect(callback).not.toHaveBeenCalled(); // foo didn't change
      expect(model.get("bar")).toBe(456);
    });

    it("should update and emit for deep changes", () => {
      const modelWithObject = new Model<{ foo: { nested: string } }>(
        { foo: { nested: "test" } },
        onChange,
        modelId,
      );
      const callback = vi.fn();
      modelWithObject.on("change:foo", callback);

      modelWithObject.updateAndEmitDiffs({ foo: { nested: "changed" } });
      expect(callback).toHaveBeenCalledTimes(1);
    });

    it("should emit change event for any changes", async () => {
      const callback = vi.fn();
      model.on("change", callback);
      model.updateAndEmitDiffs({ foo: "changed", bar: 456 });
      await TestUtils.nextTick(); // flush
      expect(callback).toHaveBeenCalledTimes(1);
    });
  });

  describe("emitCustomMessage", () => {
    it("should handle custom messages", () => {
      const callback = vi.fn();
      model.on("msg:custom", callback);

      const content = { type: "test" };
      model.emitCustomMessage({
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
      model.emitCustomMessage(
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
  const handle = ({
    modelId,
    message,
    buffers,
  }: {
    modelId: WidgetModelId;
    message: AnyWidgetMessage;
    buffers: readonly DataView[];
  }) => {
    return handleWidgetMessage({
      modelId,
      msg: message,
      buffers,
      modelManager,
    });
  };

  beforeEach(() => {
    // Clear the model manager before each test
    modelManager = new ModelManager(50);
  });

  it("should set and get models", async () => {
    const model = new Model({ count: 0 }, vi.fn(), testId);
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
    const model = new Model({ count: 0 }, vi.fn(), testId);
    modelManager.set(testId, model);
    modelManager.delete(testId);
    await expect(modelManager.get(testId)).rejects.toThrow();
  });

  it("should handle widget messages", async () => {
    const openMessage: AnyWidgetMessage = {
      method: "open",
      state: { count: 0 },
      buffer_paths: [],
    };

    await handle({ modelId: testId, message: openMessage, buffers: [] });
    const model = await modelManager.get(testId);
    expect(model.get("count")).toBe(0);

    const updateMessage: AnyWidgetMessage = {
      method: "update",
      state: {
        count: 1,
      },
      buffer_paths: [],
    };

    await handle({ modelId: testId, message: updateMessage, buffers: [] });
    expect(model.get("count")).toBe(1);
  });

  it("should handle custom messages", async () => {
    const model = new Model({ count: 0 }, vi.fn(), testId);
    const callback = vi.fn();
    model.on("msg:custom", callback);
    modelManager.set(testId, model);

    await handle({
      modelId: testId,
      message: { method: "custom", content: { count: 1 } },
      buffers: [],
    });
    expect(callback).toHaveBeenCalledWith({ count: 1 }, []);
  });

  it("should handle close messages", async () => {
    const model = new Model({ count: 0 }, vi.fn(), testId);
    modelManager.set(testId, model);

    await handle({
      modelId: testId,
      message: { method: "close" },
      buffers: [],
    });
    await expect(modelManager.get(testId)).rejects.toThrow();
  });
});
