/* Copyright 2026 Marimo. All rights reserved. */

import { render, waitFor } from "@testing-library/react";
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  type MockInstance,
  vi,
} from "vitest";
import type { IPluginProps } from "@/plugins/types";
import { visibleForTesting } from "../AnyWidgetPlugin";
import { Model } from "../model";
import { WIDGET_REGISTRY } from "../registry";
import type { EsmSpec, ModelState, WidgetModelId } from "../types";
import { WIDGET_DEF_REGISTRY } from "../widget-binding";

const { AnyWidgetSlot } = visibleForTesting;

// Helper to create typed model IDs for tests
const asModelId = (id: string): WidgetModelId => id as WidgetModelId;

function createMockComm() {
  return {
    sendUpdate: vi.fn().mockResolvedValue(undefined),
    sendCustomMessage: vi.fn().mockResolvedValue(undefined),
  };
}

function createMockModel(state?: ModelState) {
  return new Model<ModelState>(state ?? { count: 0 }, createMockComm());
}

const hostEl = () => document.createElement("div");

describe("AnyWidgetSlot", () => {
  const SPEC: EsmSpec = { url: "./@file/10-slot.js", hash: "slot-hash" };
  let getModuleSpy: MockInstance<typeof WIDGET_DEF_REGISTRY.getModule>;
  let nextId = 0;
  let modelId: WidgetModelId;
  let mockWidget: {
    initialize: ReturnType<typeof vi.fn>;
    render: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    nextId += 1;
    modelId = asModelId(`slot-test-${nextId}`);
    mockWidget = { initialize: vi.fn(), render: vi.fn() };
    getModuleSpy = vi
      .spyOn(WIDGET_DEF_REGISTRY, "getModule")
      .mockResolvedValue({ default: mockWidget });
    WIDGET_REGISTRY.setModel(modelId, createMockModel());
    WIDGET_REGISTRY.setSpec(modelId, {
      url: SPEC.url,
      // Unique hash per test so the module-cache spy is always hit.
      hash: `${SPEC.hash}-${nextId}`,
    });
  });

  afterEach(() => {
    WIDGET_REGISTRY.delete(modelId);
    getModuleSpy.mockRestore();
  });

  const props = (
    id: WidgetModelId,
    value: Record<string, unknown> = {},
  ): IPluginProps<{ model_id?: WidgetModelId }, { modelId: WidgetModelId }> =>
    ({
      data: { modelId: id },
      value,
      host: hostEl(),
      setValue: vi.fn(),
      functions: {},
    }) as unknown as IPluginProps<
      { model_id?: WidgetModelId },
      { modelId: WidgetModelId }
    >;

  it("resolves the widget through the registry and renders a view", async () => {
    render(<AnyWidgetSlot {...props(modelId)} />);
    await waitFor(() => {
      expect(mockWidget.initialize).toHaveBeenCalledTimes(1);
      expect(mockWidget.render).toHaveBeenCalledTimes(1);
    });
  });

  it("aborts the runtime-owned view on unmount", async () => {
    const { unmount } = render(<AnyWidgetSlot {...props(modelId)} />);
    await waitFor(() => {
      expect(mockWidget.render).toHaveBeenCalledTimes(1);
    });
    const signal = mockWidget.render.mock.calls[0][0].signal as AbortSignal;
    expect(signal.aborted).toBe(false);
    unmount();
    expect(signal.aborted).toBe(true);
  });

  it("does not remount when only the value changes", async () => {
    // Regression: a state update rewrites the plugin value (dropping
    // model_id), but the key comes from data attributes, so the view
    // must survive.
    const { container, rerender } = render(
      <AnyWidgetSlot {...props(modelId)} />,
    );
    await waitFor(() => {
      expect(mockWidget.render).toHaveBeenCalledTimes(1);
    });
    const divBefore = container.querySelector("div");

    rerender(<AnyWidgetSlot {...props(modelId, { zoom_level: 0 })} />);

    await waitFor(() => {
      expect(container.querySelector("div")).toBe(divBefore);
      expect(mockWidget.render).toHaveBeenCalledTimes(1);
    });
  });

  it("remounts and re-initializes when modelId changes (cell re-run)", async () => {
    // Regression for marimo-team/marimo#3962: a cell re-run reconstructs
    // the widget, opening a new comm with a new model id. The plugin
    // must remount so initialize runs against the fresh model.
    const { rerender } = render(<AnyWidgetSlot {...props(modelId)} />);
    await waitFor(() => {
      expect(mockWidget.render).toHaveBeenCalledTimes(1);
    });

    const rerunId = asModelId(`slot-test-${nextId}-rerun`);
    WIDGET_REGISTRY.setModel(rerunId, createMockModel());
    WIDGET_REGISTRY.setSpec(rerunId, {
      url: SPEC.url,
      hash: `${SPEC.hash}-${nextId}-rerun`,
    });
    try {
      rerender(<AnyWidgetSlot {...props(rerunId)} />);
      await waitFor(() => {
        expect(mockWidget.initialize).toHaveBeenCalledTimes(2);
        expect(mockWidget.render).toHaveBeenCalledTimes(2);
      });
    } finally {
      WIDGET_REGISTRY.delete(rerunId);
    }
  });

  it("shows an error banner when the widget cannot be resolved", async () => {
    getModuleSpy.mockRejectedValue(new Error("import failed"));
    const { container } = render(<AnyWidgetSlot {...props(modelId)} />);
    await waitFor(() => {
      expect(container.textContent).toContain("import failed");
    });
  });

  it("shows an error banner when render fails", async () => {
    mockWidget.render.mockRejectedValue(new Error("widget exploded"));
    const { container } = render(<AnyWidgetSlot {...props(modelId)} />);
    await waitFor(() => {
      expect(container.textContent).toContain("widget exploded");
    });
  });
});
