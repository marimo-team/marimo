/* Copyright 2024 Marimo. All rights reserved. */
import { getDirtyFields, visibleForTesting } from "../AnyWidgetPlugin";
import { Model } from "../model";
import { vi, describe, it, expect, beforeEach } from "vitest";
import { render, act, waitFor } from "@testing-library/react";
import { MarimoIncomingMessageEvent } from "@/core/dom/events";
import type { UIElementId } from "@/core/cells/ids";

const { LoadedSlot } = visibleForTesting;

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
