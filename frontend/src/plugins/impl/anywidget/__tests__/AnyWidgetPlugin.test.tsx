/* Copyright 2026 Marimo. All rights reserved. */

import { render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TestUtils } from "@/__tests__/test-helpers";
import type { HTMLElementNotDerivedFromRef } from "@/hooks/useEventListener";
import { visibleForTesting } from "../AnyWidgetPlugin";
import { MODEL_MANAGER, Model } from "../model";
import type { WidgetModelId } from "../types";
import { BINDING_MANAGER } from "../widget-binding";

const { LoadedSlot, isAnyWidgetModule, getInvalidAnyWidgetModuleError } =
  visibleForTesting;

// Helper to create typed model IDs for tests
const asModelId = (id: string): WidgetModelId => id as WidgetModelId;

// Mock a minimal AnyWidget implementation
const mockWidget = {
  initialize: vi.fn(),
  render: vi.fn(),
};

describe("LoadedSlot", () => {
  const modelId = asModelId("test-model-id");
  let mockModel: Model<{ count: number }>;

  const mockProps = {
    widget: mockWidget,
    data: {
      jsUrl: "http://example.com/widget.js",
      jsHash: "abc123",
      modelId: modelId,
    },
    host: document.createElement(
      "div",
    ) as unknown as HTMLElementNotDerivedFromRef,
    modelId: modelId,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Create and register a mock model before each test
    mockModel = new Model(
      { count: 0 },
      {
        sendUpdate: vi.fn().mockResolvedValue(undefined),
        sendCustomMessage: vi.fn().mockResolvedValue(undefined),
      },
    );
    MODEL_MANAGER.set(modelId, mockModel);
  });

  afterEach(() => {
    BINDING_MANAGER.destroy(modelId);
  });

  it("should render a div with ref", () => {
    const { container } = render(<LoadedSlot {...mockProps} />);
    expect(container.querySelector("div")).not.toBeNull();
  });

  it("should call runAnyWidgetModule on initialization", async () => {
    render(<LoadedSlot {...mockProps} />);

    // Wait a render
    await waitFor(() => {
      expect(mockWidget.render).toHaveBeenCalled();
    });
  });

  it("should not remount when value update drops model_id", async () => {
    // Regression: when the frontend sends a state update (e.g. {zoom_level: 0}),
    // it overwrites the UIElement value that originally held {model_id: "..."}.
    // The key must stay stable because modelId comes from data, not value.
    const { container, rerender } = render(<LoadedSlot {...mockProps} />);

    await waitFor(() => {
      expect(mockWidget.render).toHaveBeenCalledTimes(1);
    });

    const divBefore = container.querySelector("div");

    // Simulate a value update that does NOT include model_id
    // (this is what happens when the widget sends trait state)
    rerender(<LoadedSlot {...mockProps} />);

    await waitFor(() => {
      // The div should be the same DOM node (no remount)
      expect(container.querySelector("div")).toBe(divBefore);
      // render should not be called again (no remount)
      expect(mockWidget.render).toHaveBeenCalledTimes(1);
    });
  });

  it("should re-run widget when widget prop changes", async () => {
    const { rerender } = render(<LoadedSlot {...mockProps} />);

    // Wait for initial render
    await waitFor(() => {
      expect(mockWidget.render).toHaveBeenCalled();
    });

    // Create a new widget mock
    const newMockWidget = {
      initialize: vi.fn(),
      render: vi.fn(),
    };

    // Change the widget
    rerender(<LoadedSlot {...mockProps} widget={newMockWidget} />);
    await TestUtils.nextTick();

    // Wait for re-render with new widget
    await waitFor(() => {
      expect(newMockWidget.render).toHaveBeenCalled();
    });
  });

  it("should hydrate view state even when listener attaches late", async () => {
    mockModel = new Model(
      { count: 8 },
      {
        sendUpdate: vi.fn().mockResolvedValue(undefined),
        sendCustomMessage: vi.fn().mockResolvedValue(undefined),
      },
    );
    MODEL_MANAGER.set(modelId, mockModel);

    const lateListenerWidget = {
      initialize: vi.fn(),
      render: vi.fn(({ model, el }) => {
        // Simulate a widget view that starts with a local default and
        // relies on change events for hydration.
        el.textContent = "count is 5";
        const onCount = () => {
          el.textContent = `count is ${model.get("count")}`;
        };
        model.on("change:count", onCount);
        return () => model.off("change:count", onCount);
      }),
    };

    const { container } = render(
      <LoadedSlot {...mockProps} widget={lateListenerWidget} />,
    );

    await waitFor(() => {
      expect(lateListenerWidget.render).toHaveBeenCalled();
      expect(container.textContent).toContain("count is 8");
    });
  });
});

describe("isAnyWidgetModule", () => {
  it("should accept a default object with render", () => {
    expect(isAnyWidgetModule({ default: { render: () => undefined } })).toBe(
      true,
    );
  });

  it("should accept a default factory function", () => {
    expect(
      isAnyWidgetModule({ default: async () => ({ render: () => {} }) }),
    ).toBe(true);
  });

  it("should reject legacy named render exports", () => {
    expect(isAnyWidgetModule({ render: () => undefined })).toBe(false);
  });
});

describe("getInvalidAnyWidgetModuleError", () => {
  const jsUrl = "./@file/widget.js";

  it("should explain legacy named render exports", () => {
    const error = getInvalidAnyWidgetModuleError(
      { render: () => undefined },
      jsUrl,
    );
    expect(error.message).toContain("named exports (`render`)");
    expect(error.message).toContain("`export default { render }`");
    expect(error.message).toContain("not `export function render`");
  });

  it("should explain legacy named initialize exports", () => {
    const error = getInvalidAnyWidgetModuleError(
      { initialize: () => undefined },
      jsUrl,
    );
    expect(error.message).toContain("named exports (`initialize`)");
    expect(error.message).toContain("`export default { initialize }`");
    expect(error.message).toContain("not `export function initialize`");
  });

  it("should explain a missing default export", () => {
    expect(getInvalidAnyWidgetModuleError({}, jsUrl).message).toContain(
      "missing a default export",
    );
    expect(getInvalidAnyWidgetModuleError(null, jsUrl).message).toContain(
      "missing a default export",
    );
  });

  it("should explain an invalid default export", () => {
    const error = getInvalidAnyWidgetModuleError({ default: {} }, jsUrl);
    expect(error.message).toContain("invalid default export");
    expect(error.message).toContain("https://anywidget.dev/en/afm/");
  });
});
