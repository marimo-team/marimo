/* Copyright 2024 Marimo. All rights reserved. */
import { getDirtyFields } from "../AnyWidgetPlugin";
import { Model } from "../model";
import { vi, describe, it, expect, beforeEach } from "vitest";

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
    it("should throw error when accessing widget_manager", () => {
      expect(() => model.widget_manager.get_model("foo")).toThrow(
        "widget_manager not supported in marimo",
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

describe("getDirtyFields", () => {
  it("should return empty set when values are equal", () => {
    const value = { foo: "bar", baz: 123 };
    const initialValue = { foo: "bar", baz: 123 };

    const result = getDirtyFields(value, initialValue);

    expect(result.size).toBe(0);
  });

  it("should return keys of changed values", () => {
    const value = { foo: "changed", baz: 123 };
    const initialValue = { foo: "bar", baz: 123 };

    const result = getDirtyFields(value, initialValue);

    expect(result.size).toBe(1);
    expect(result.has("foo")).toBe(true);
  });

  it("should handle multiple changed values", () => {
    const value = { foo: "changed", baz: 456, extra: "new" };
    const initialValue = { foo: "bar", baz: 123, extra: "old" };

    const result = getDirtyFields(value, initialValue);

    expect(result.size).toBe(3);
    expect(result.has("foo")).toBe(true);
    expect(result.has("baz")).toBe(true);
    expect(result.has("extra")).toBe(true);
  });

  it("should handle nested objects correctly", () => {
    const value = { foo: "bar", nested: { a: 1, b: 2 } };
    const initialValue = { foo: "bar", nested: { a: 1, b: 3 } };

    const result = getDirtyFields(value, initialValue);

    expect(result.size).toBe(1);
    expect(result.has("nested")).toBe(true);
  });

  it("should handle subset of initial fields", () => {
    const value = { foo: "bar", baz: 123 };
    const initialValue = { foo: "bar", baz: 123, full: "value" };

    const result = getDirtyFields(value, initialValue);
    expect(result.size).toBe(0);
  });
});
