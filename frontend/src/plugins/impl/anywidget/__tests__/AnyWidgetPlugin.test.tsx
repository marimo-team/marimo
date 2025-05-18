/* Copyright 2024 Marimo. All rights reserved. */
import { getDirtyFields, visibleForTesting } from "../AnyWidgetPlugin";
import { Model } from "../model";
import { vi, describe, it, expect, beforeEach } from "vitest";
import { render, act, waitFor } from "@testing-library/react";
import { MarimoIncomingMessageEvent } from "@/core/dom/events";
import type { UIElementId } from "@/core/cells/ids";

const { LoadedSlot } = visibleForTesting;

const modelId = "test-model-id";

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
      modelId,
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
      const modelId = "test-model-id";
      const modelWithObject = new Model<{ foo: { nested: string } }>(
        { foo: { nested: "test" } },
        modelId,
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

// Mock a minimal AnyWidget implementation
const mockWidget = {
  initialize: vi.fn(),
  render: vi.fn(),
};

vi.mock("../AnyWidgetPlugin", async () => {
  const originalModule = await vi.importActual("../AnyWidgetPlugin");
  return {
    ...originalModule,
    runAnyWidgetModule: vi.fn(),
  };
});

describe("LoadedSlot", () => {
  const mockProps = {
    value: { count: 0 },
    setValue: vi.fn(),
    widget: mockWidget,
    functions: {
      send_to_widget: vi.fn().mockResolvedValue(null),
    },
    data: {
      jsUrl: "http://example.com/widget.js",
      jsHash: "abc123",
      initialValue: { count: 0 },
    },
    host: document.createElement("div"),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render a div with ref", () => {
    const { container } = render(<LoadedSlot {...mockProps} />);
    expect(container.querySelector("div")).not.toBeNull();
  });

  it("should initialize model with merged values", () => {
    const modelSpy = vi.spyOn(Model.prototype, "updateAndEmitDiffs");
    render(<LoadedSlot {...mockProps} />);

    expect(modelSpy).toHaveBeenCalledExactlyOnceWith({ count: 0 });
  });

  it("should update model when value prop changes", async () => {
    const { rerender } = render(<LoadedSlot {...mockProps} />);
    const modelSpy = vi.spyOn(Model.prototype, "updateAndEmitDiffs");

    // Update the value prop
    rerender(<LoadedSlot {...mockProps} value={{ count: 5 }} />);

    // Model should be updated with the new value
    expect(modelSpy).toHaveBeenCalledWith({ count: 5 });
  });

  it("should listen for incoming messages", async () => {
    render(<LoadedSlot {...mockProps} />);

    // Send a mock message
    const mockMessageEvent = MarimoIncomingMessageEvent.create({
      detail: {
        objectId: "test-id" as UIElementId,
        message: {
          method: "update",
          state: { count: 10 },
        },
        buffers: undefined,
      },
      bubbles: false,
      composed: true,
    });
    const updateAndEmitDiffsSpy = vi.spyOn(Model.prototype, "set");

    // Dispatch the event on the host element
    act(() => {
      mockProps.host.dispatchEvent(mockMessageEvent);
    });

    await waitFor(() => {
      expect(updateAndEmitDiffsSpy).toHaveBeenCalledWith("count", 10);
    });
  });

  it("should call runAnyWidgetModule on initialization", async () => {
    const { rerender } = render(<LoadedSlot {...mockProps} />);

    // Wait a render
    await waitFor(() => {
      expect(mockWidget.render).toHaveBeenCalled();
    });

    // Render without any prop changes
    rerender(<LoadedSlot {...mockProps} />);
    await new Promise((resolve) => setTimeout(resolve, 0));

    // Still only called once
    expect(mockWidget.render).toHaveBeenCalledTimes(1);

    // Change the jsUrl
    rerender(
      <LoadedSlot
        {...mockProps}
        data={{
          ...mockProps.data,
          jsUrl: "http://example.com/widget-updated.js",
        }}
      />,
    );
    await new Promise((resolve) => setTimeout(resolve, 0));

    // Wait a render
    await waitFor(() => {
      expect(mockWidget.render).toHaveBeenCalledTimes(2);
    });
  });
});
