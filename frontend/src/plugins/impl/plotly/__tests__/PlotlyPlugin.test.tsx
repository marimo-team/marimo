/* Copyright 2026 Marimo. All rights reserved. */

import { act, render, waitFor } from "@testing-library/react";
import { Suspense } from "react";
import { describe, expect, it, vi } from "vitest";
import { SetupMocks } from "@/__mocks__/common";
import type { Setter } from "@/plugins/types";
import { PlotlyComponent } from "../PlotlyPlugin";

SetupMocks.resizeObserver();

type CapturedPlotProps = {
  onClick?: (event: {
    points: {
      data?: { type?: string };
      x?: string | number;
      y?: string | number;
      pointIndex?: number;
      pointNumber?: number;
      curveNumber?: number;
    }[];
  }) => void;
} | null;

let capturedPlotProps: CapturedPlotProps = null;

vi.mock("../Plot", () => ({
  Plot: (props: CapturedPlotProps) => {
    capturedPlotProps = props;
    return <div data-testid="plotly-mock" />;
  },
}));

vi.mock("../usePlotlyLayout", () => ({
  usePlotlyLayout: ({
    originalFigure,
  }: {
    originalFigure: {
      data: unknown[];
      layout: Record<string, unknown>;
      frames: unknown[] | null;
    };
  }) => ({
    figure: originalFigure,
    layout: originalFigure.layout,
    handleReset: vi.fn(),
  }),
}));

vi.mock("@/hooks/useScript", () => ({
  useScript: () => "ready",
}));

vi.mock("react-use-event-hook", () => ({
  default: <T,>(callback: T) => callback,
}));

describe("PlotlyPlugin", () => {
  it("clicking a bar selects that bar", async () => {
    const setValue = vi.fn<Setter<unknown>>();

    render(
      <Suspense fallback={null}>
        <PlotlyComponent
          figure={{
            data: [{ type: "bar" }],
            layout: {},
            frames: null,
          }}
          value={undefined}
          setValue={setValue}
          host={document.createElement("div")}
          config={{}}
        />
      </Suspense>,
    );

    await waitFor(() => {
      expect(capturedPlotProps).not.toBeNull();
    });

    act(() => {
      capturedPlotProps?.onClick?.({
        points: [
          {
            data: { type: "bar" },
            x: "Feb",
            y: 18,
            pointIndex: 1,
            pointNumber: 1,
            curveNumber: 0,
          },
        ],
      });
    });

    expect(setValue).toHaveBeenCalledTimes(1);
    const updater = setValue.mock.calls[0][0] as (value: unknown) => unknown;
    expect(updater({})).toEqual({
      selections: [],
      points: [
        {
          x: "Feb",
          y: 18,
          curveNumber: 0,
          pointNumber: 1,
          pointIndex: 1,
        },
      ],
      indices: [1],
      range: undefined,
    });
  });
});
