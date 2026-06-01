/* Copyright 2026 Marimo. All rights reserved. */

import { act, render, waitFor } from "@testing-library/react";
import { Suspense } from "react";
import { describe, expect, it, vi } from "vitest";
import { SetupMocks } from "@/__mocks__/common";
import type { Setter } from "@/plugins/types";
import type { SelectedPoint } from "../Plot";
import { PlotlyComponent } from "../PlotlyPlugin";

SetupMocks.resizeObserver();

type CapturedPlotProps = {
  hasSelection?: boolean;
  selectedPoints?: ReadonlyArray<SelectedPoint>;
  layoutSelections?: ReadonlyArray<unknown>;
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
  onDeselect?: () => void;
  onSelected?: (event: {
    points: {
      data?: { type?: string };
      x?: string | number;
      y?: string | number;
      pointIndex?: number;
      pointNumber?: number;
      curveNumber?: number;
    }[];
    range?: { x?: number[]; y?: number[] };
    lassoPoints?: { x?: unknown[]; y?: unknown[] };
    selections?: unknown[];
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

  it("clicking a box element triggers onClick", async () => {
    const setValue = vi.fn<Setter<unknown>>();

    render(
      <Suspense fallback={null}>
        <PlotlyComponent
          figure={{
            data: [{ type: "box" }],
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
            data: { type: "box" },
            x: "Group A",
            y: 3,
            pointIndex: 0,
            pointNumber: 0,
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
        { x: "Group A", y: 3, curveNumber: 0, pointNumber: 0, pointIndex: 0 },
      ],
      indices: [0],
      range: undefined,
    });
  });

  it("selectedPoints is forwarded to Plot so greyout stays in sync", async () => {
    const setValue = vi.fn<Setter<unknown>>();

    const points = [
      { x: "Feb", y: 18, curveNumber: 0, pointIndex: 1, pointNumber: 1 },
    ];

    render(
      <Suspense fallback={null}>
        <PlotlyComponent
          figure={{ data: [{ type: "bar" }], layout: {}, frames: null }}
          value={{ points, indices: [1] }}
          setValue={setValue}
          host={document.createElement("div")}
          config={{}}
        />
      </Suspense>,
    );

    await waitFor(() => {
      expect(capturedPlotProps).not.toBeNull();
    });
    expect(capturedPlotProps?.selectedPoints).toEqual(points);
  });

  it("click handler empties layoutSelections so Plot can clear the box/lasso overlay", async () => {
    const setValue = vi.fn<Setter<unknown>>();

    render(
      <Suspense fallback={null}>
        <PlotlyComponent
          figure={{ data: [{ type: "bar" }], layout: {}, frames: null }}
          value={{
            selections: [{ type: "rect", x0: 0, x1: 1, y0: 0, y1: 1 }],
            range: { x: [0, 1], y: [0, 1] },
          }}
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
    const updater = setValue.mock.calls[0][0] as (
      value: Record<string, unknown>,
    ) => Record<string, unknown>;
    const next = updater({
      selections: [{ type: "rect", x0: 0, x1: 1, y0: 0, y1: 1 }],
      range: { x: [0, 1], y: [0, 1] },
    });
    expect(next.selections).toEqual([]);
    expect(next.range).toBeUndefined();
    expect(next.lasso).toBeUndefined();
    expect(next.points).toEqual([
      { x: "Feb", y: 18, curveNumber: 0, pointNumber: 1, pointIndex: 1 },
    ]);
  });

  it("onSelected treats a single-point event with no range/lasso as a click replacement", async () => {
    const setValue = vi.fn<Setter<unknown>>();

    render(
      <Suspense fallback={null}>
        <PlotlyComponent
          figure={{ data: [{ type: "scatter" }], layout: {}, frames: null }}
          value={{
            selections: [{ type: "rect", x0: 0, x1: 1, y0: 0, y1: 1 }],
            range: { x: [0, 1], y: [0, 1] },
            points: [{ x: 0.5, y: 0.5, curveNumber: 0, pointIndex: 42 }],
            indices: [42],
          }}
          setValue={setValue}
          host={document.createElement("div")}
          config={{}}
        />
      </Suspense>,
    );

    await waitFor(() => {
      expect(capturedPlotProps).not.toBeNull();
    });

    // Single click on a scatter point after a box selection: plotly_selected
    // still echoes evt.selections from the old box, but no range/lassoPoints.
    act(() => {
      capturedPlotProps?.onSelected?.({
        points: [
          {
            data: { type: "scatter" },
            x: 2.6,
            y: 7.7,
            pointIndex: 108,
            pointNumber: 108,
            curveNumber: 2,
          },
        ],
        selections: [{ type: "rect", x0: 0, x1: 1, y0: 0, y1: 1 }],
      });
    });

    expect(setValue).toHaveBeenCalledTimes(1);
    const updater = setValue.mock.calls[0][0] as (
      value: Record<string, unknown>,
    ) => Record<string, unknown>;
    const next = updater({});
    expect(next.selections).toEqual([]);
    expect(next.range).toBeUndefined();
    expect(next.lasso).toBeUndefined();
    expect(next.indices).toEqual([108]);
    expect((next.points as Array<Record<string, unknown>>)[0]).toMatchObject({
      x: 2.6,
      y: 7.7,
      curveNumber: 2,
      pointIndex: 108,
    });
  });

  it("onSelected preserves range/selections for a box selection", async () => {
    const setValue = vi.fn<Setter<unknown>>();

    render(
      <Suspense fallback={null}>
        <PlotlyComponent
          figure={{ data: [{ type: "scatter" }], layout: {}, frames: null }}
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

    const boxSelections = [{ type: "rect", x0: 3, x1: 4, y0: 5, y1: 8 }];
    const boxRange = { x: [3, 4], y: [5, 8] };
    act(() => {
      capturedPlotProps?.onSelected?.({
        points: [
          {
            data: { type: "scatter" },
            x: 3.5,
            y: 6,
            pointIndex: 0,
            pointNumber: 0,
            curveNumber: 0,
          },
          {
            data: { type: "scatter" },
            x: 3.8,
            y: 7,
            pointIndex: 1,
            pointNumber: 1,
            curveNumber: 0,
          },
        ],
        range: boxRange,
        selections: boxSelections,
      });
    });

    expect(setValue).toHaveBeenCalledTimes(1);
    const updater = setValue.mock.calls[0][0] as (
      value: Record<string, unknown>,
    ) => Record<string, unknown>;
    const next = updater({});
    expect(next.selections).toEqual(boxSelections);
    expect(next.range).toEqual(boxRange);
    expect(next.lasso).toBeUndefined();
    expect(next.indices).toEqual([0, 1]);
  });

  it("hasSelection reflects current selection state", async () => {
    const setValue = vi.fn<Setter<unknown>>();

    const { rerender } = render(
      <Suspense fallback={null}>
        <PlotlyComponent
          figure={{ data: [{ type: "scatter" }], layout: {}, frames: null }}
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
    expect(capturedPlotProps?.hasSelection).toBe(false);

    rerender(
      <Suspense fallback={null}>
        <PlotlyComponent
          figure={{ data: [{ type: "scatter" }], layout: {}, frames: null }}
          value={{ points: [{ x: 1, y: 2 }], indices: [0] }}
          setValue={setValue}
          host={document.createElement("div")}
          config={{}}
        />
      </Suspense>,
    );
    await waitFor(() => {
      expect(capturedPlotProps?.hasSelection).toBe(true);
    });

    rerender(
      <Suspense fallback={null}>
        <PlotlyComponent
          figure={{ data: [{ type: "scatter" }], layout: {}, frames: null }}
          value={{ range: { x: [0, 1], y: [0, 1] } }}
          setValue={setValue}
          host={document.createElement("div")}
          config={{}}
        />
      </Suspense>,
    );
    await waitFor(() => {
      expect(capturedPlotProps?.hasSelection).toBe(true);
    });

    rerender(
      <Suspense fallback={null}>
        <PlotlyComponent
          figure={{ data: [{ type: "scatter" }], layout: {}, frames: null }}
          value={{ lasso: { x: [0], y: [0] } }}
          setValue={setValue}
          host={document.createElement("div")}
          config={{}}
        />
      </Suspense>,
    );
    await waitFor(() => {
      expect(capturedPlotProps?.hasSelection).toBe(true);
    });
  });

  it("onDeselect clears all selection state (shared by double-click and Escape)", async () => {
    const setValue = vi.fn<Setter<unknown>>();

    render(
      <Suspense fallback={null}>
        <PlotlyComponent
          figure={{ data: [{ type: "scatter" }], layout: {}, frames: null }}
          value={{
            points: [{ x: 1, y: 2 }],
            indices: [0],
            range: { x: [0, 1], y: [0, 1] },
            lasso: { x: [0], y: [0] },
            selections: [{ type: "rect" }],
            dragmode: "select",
          }}
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
      capturedPlotProps?.onDeselect?.();
    });

    expect(setValue).toHaveBeenCalledTimes(1);
    const updater = setValue.mock.calls[0][0] as (
      value: Record<string, unknown>,
    ) => unknown;
    expect(
      updater({
        points: [{ x: 1, y: 2 }],
        indices: [0],
        range: { x: [0, 1], y: [0, 1] },
        lasso: { x: [0], y: [0] },
        selections: [{ type: "rect" }],
        dragmode: "select",
      }),
    ).toEqual({
      points: [],
      indices: [],
      selections: [],
      range: undefined,
      lasso: undefined,
      dragmode: "select",
    });
  });

  it("clicking a violin element triggers onClick", async () => {
    const setValue = vi.fn<Setter<unknown>>();

    render(
      <Suspense fallback={null}>
        <PlotlyComponent
          figure={{
            data: [{ type: "violin" }],
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
            data: { type: "violin" },
            x: "Group A",
            y: 3,
            pointIndex: 0,
            pointNumber: 0,
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
        { x: "Group A", y: 3, curveNumber: 0, pointNumber: 0, pointIndex: 0 },
      ],
      indices: [0],
      range: undefined,
    });
  });
});
