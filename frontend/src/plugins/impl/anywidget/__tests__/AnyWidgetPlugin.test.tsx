/* Copyright 2026 Marimo. All rights reserved. */

import { render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TestUtils } from "@/__tests__/test-helpers";
import type { HTMLElementNotDerivedFromRef } from "@/hooks/useEventListener";
import { visibleForTesting } from "../AnyWidgetPlugin";
import { MODEL_MANAGER, Model } from "../model";
import type { WidgetModelId } from "../types";
import { BINDING_MANAGER } from "../widget-binding";

const { LoadedSlot } = visibleForTesting;

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
});
