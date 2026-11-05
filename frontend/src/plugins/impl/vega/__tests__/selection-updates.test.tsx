/* Copyright 2026 Marimo. All rights reserved. */
import { act, cleanup, render, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import VegaComponent, { type VegaComponentState } from "../vega-component";

const { listeners, embed } = vi.hoisted(() => {
  const listeners = new Map<string, (name: string, value: unknown) => void>();
  const embed = {
    view: {
      addSignalListener: vi.fn(
        (name: string, handler: (name: string, value: unknown) => void) => {
          listeners.set(name, handler);
        },
      ),
      removeSignalListener: vi.fn((name: string) => {
        listeners.delete(name);
      }),
    },
  };
  return { listeners, embed };
});

vi.mock("react-vega", () => ({
  useVegaEmbed: () => embed,
}));

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  listeners.clear();
});

describe("Altair selection updates", () => {
  it("does not resend equal selections after re-render", async () => {
    const onChange = vi.fn();
    function Chart() {
      const [value, setValue] = useState<VegaComponentState>({});
      return (
        <VegaComponent
          spec={{
            data: { values: [{ x: 1, y: 2 }] },
            mark: "point",
            encoding: {
              x: { field: "x", type: "quantitative" },
              y: { field: "y", type: "quantitative" },
            },
          }}
          chartSelection="interval"
          fieldSelection={false}
          value={value}
          setValue={(next) => {
            onChange(next);
            setValue(next);
          }}
        />
      );
    }
    const view = render(<Chart />, { wrapper: TooltipProvider });
    await waitFor(() => expect(listeners.has("select_interval")).toBe(true));
    vi.useFakeTimers();

    const emit = async (value: unknown) => {
      await act(async () => {
        const handler = listeners.get("select_interval");
        expect(handler).toBeDefined();
        handler?.("select_interval", value);
        await vi.advanceTimersByTimeAsync(100);
      });
    };

    await act(async () => {
      listeners.get("select_interval")?.("select_interval", { x: [1, 2] });
      await vi.advanceTimersByTimeAsync(99);
    });
    expect(onChange).not.toHaveBeenCalled();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(onChange.mock.calls).toEqual([[{ select_interval: { x: [1, 2] } }]]);

    view.rerender(<Chart />);
    await emit({ x: [1, 2] });
    await emit({ x: [1, 2] });
    expect(onChange).toHaveBeenCalledTimes(1);

    await emit({ x: [1, 3] });
    await emit({});
    await emit({});
    expect(onChange.mock.calls).toEqual([
      [{ select_interval: { x: [1, 2] } }],
      [{ select_interval: { x: [1, 3] } }],
      [{ select_interval: {} }],
    ]);
  });
});
