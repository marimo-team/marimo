/* Copyright 2024 Marimo. All rights reserved. */
import {
  describe,
  beforeEach,
  it,
  expect,
  vi,
  afterAll,
  beforeAll,
} from "vitest";
import {
  Model,
  handleWidgetMessage,
  type AnyWidgetMessage,
  visibleForTesting,
} from "../model";
import type { Base64String } from "@/utils/json/base64";

const { ModelManager } = visibleForTesting;

describe("Model", () => {
  let model: Model<{ foo: string; bar: number }>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let onChange: (value: any) => void;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let sendToWidget: (req: { content?: any }) => Promise<null | undefined>;

  beforeEach(() => {
    onChange = vi.fn();
    sendToWidget = vi.fn().mockResolvedValue(null);
    model = new Model(
      { foo: "test", bar: 123 },
      onChange,
      sendToWidget,
      new Set(),
    );
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

    it("should send all dirty fields", () => {
      model.set("foo", "new value");
      model.save_changes();

      expect(onChange).toHaveBeenCalledWith({
        foo: "new value",
      });

      model.set("bar", 456);
      model.save_changes();

      expect(onChange).toHaveBeenCalledWith({
        foo: "new value",
        bar: 456,
      });
    });

    // Skip because we don't clear the dirty fields after save
    it.skip("should clear dirty fields after save", () => {
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

      expect(sendToWidget).toHaveBeenCalledWith({ content: { test: true } });
      await new Promise((resolve) => setTimeout(resolve, 0)); // flush
      expect(callback).toHaveBeenCalledWith(null);
    });

    it("should warn when buffers are provided", () => {
      const consoleSpy = vi.spyOn(console, "warn").mockImplementation(() => {
        // noop
      });
      model.send({ test: true }, null, [new ArrayBuffer(8)]);

      expect(consoleSpy).toHaveBeenCalledWith(
        "buffers not supported in marimo anywidget.send",
      );
    });
  });

  describe("widget_manager", () => {
    const childModelId = "test-id";
    const childModel = new Model({ foo: "test" }, vi.fn(), vi.fn(), new Set());
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
      await expect(model.widget_manager.get_model("random-id")).rejects.toThrow(
        "Model not found for key: random-id",
      );
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
        sendToWidget,
        new Set(),
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
      await new Promise((resolve) => setTimeout(resolve, 0)); // flush
      expect(callback).toHaveBeenCalledTimes(1);
    });
  });

  describe("receiveCustomMessage", () => {
    it("should handle update messages", () => {
      model.receiveCustomMessage({
        method: "update",
        state: { foo: "updated", bar: 789 },
      });

      expect(model.get("foo")).toBe("updated");
      expect(model.get("bar")).toBe(789);
    });

    it("should handle custom messages", () => {
      const callback = vi.fn();
      model.on("msg:custom", callback);

      const content = { type: "test" };
      model.receiveCustomMessage({
        method: "custom",
        content,
      });

      expect(callback).toHaveBeenCalledWith(content, undefined);
    });

    it("should handle custom messages with buffers", () => {
      const callback = vi.fn();
      model.on("msg:custom", callback);

      const content = { type: "test" };
      const buffer = new DataView(new ArrayBuffer(8));
      model.receiveCustomMessage(
        {
          method: "custom",
          content,
        },
        [buffer],
      );

      expect(callback).toHaveBeenCalledWith(content, [buffer]);
    });

    it("should log error for invalid messages", () => {
      const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {
        // noop
      });
      model.receiveCustomMessage({ invalid: "message" });

      expect(consoleSpy).toHaveBeenCalledTimes(2);
    });
  });
});

describe("ModelManager", () => {
  let modelManager = new ModelManager(50);
  const handle = (
    modelId: string,
    message: AnyWidgetMessage,
    buffers: Base64String[],
  ) => {
    return handleWidgetMessage(modelId, message, buffers, modelManager);
  };

  beforeEach(() => {
    // Clear the model manager before each test
    modelManager = new ModelManager(50);
  });

  it("should set and get models", async () => {
    const model = new Model({ count: 0 }, vi.fn(), vi.fn(), new Set());
    modelManager.set("test-id", model);
    const retrievedModel = await modelManager.get("test-id");
    expect(retrievedModel).toBe(model);
  });

  it("should handle model not found", async () => {
    await expect(modelManager.get("non-existent")).rejects.toThrow(
      "Model not found for key: non-existent",
    );
  });

  it("should delete models", async () => {
    const model = new Model({ count: 0 }, vi.fn(), vi.fn(), new Set());
    modelManager.set("test-id", model);
    modelManager.delete("test-id");
    await expect(modelManager.get("test-id")).rejects.toThrow();
  });

  it("should handle widget messages", async () => {
    const openMessage: AnyWidgetMessage = {
      method: "open",
      state: { count: 0 },
      buffer_paths: [],
    };

    await handle("test-id", openMessage, []);
    const model = await modelManager.get("test-id");
    expect(model.get("count")).toBe(0);

    const updateMessage: AnyWidgetMessage = {
      method: "update",
      state: { count: 1 },
      buffer_paths: [],
    };

    await handle("test-id", updateMessage, []);
    expect(model.get("count")).toBe(1);
  });

  it("should handle close messages", async () => {
    const model = new Model({ count: 0 }, vi.fn(), vi.fn(), new Set());
    modelManager.set("test-id", model);

    await handle("test-id", { method: "close" }, []);
    await expect(modelManager.get("test-id")).rejects.toThrow();
  });
});
