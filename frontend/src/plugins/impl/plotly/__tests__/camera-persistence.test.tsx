/* Copyright 2026 Marimo. All rights reserved. */

import { act, render, waitFor } from "@testing-library/react";
import { Suspense, useEffect, useState } from "react";
import type * as Plotly from "plotly.js";
import { describe, expect, it, vi } from "vitest";
import type { Figure, PlotProps } from "../Plot";
import { PlotlyComponent } from "../PlotlyPlugin";

let plotProps: PlotProps | undefined;

// WebGL rendering is outside this test; exercise the real plugin and layout hook.
vi.mock("../Plot", () => ({
  Plot: (props: PlotProps) => {
    plotProps = props;
    return null;
  },
}));

vi.mock("@/hooks/useScript", () => ({ useScript: () => "ready" }));

type Value = React.ComponentProps<typeof PlotlyComponent>["value"];

const initialCamera = { eye: { x: 1, y: 1, z: 1 } };
const movedCamera = { eye: { x: 2, y: -1, z: 0.5 } };

function figure(revision: string | undefined = "keep-camera"): Figure {
  return {
    data: [
      {
        type: "surface",
        z: [
          [1, 2],
          [3, 4],
        ],
      },
    ],
    layout: { uirevision: revision, scene: { camera: initialCamera } },
    frames: null,
  };
}

function mountChart(data: Figure, initialValue?: Value) {
  let persistedValue = initialValue;
  let resetValue: (() => void) | undefined;
  function Chart({ figure }: { figure: Figure }) {
    const [value, setValue] = useState(initialValue);
    useEffect(() => {
      persistedValue = value;
      resetValue = () => setValue(undefined);
    }, [value]);
    return (
      <Suspense fallback={null}>
        <PlotlyComponent
          figure={figure}
          value={value}
          setValue={setValue}
          config={{}}
          host={document.createElement("div")}
        />
      </Suspense>
    );
  }
  plotProps = undefined;
  const chart = render(<Chart figure={data} />);
  return {
    ...chart,
    getValue: () => persistedValue,
    update: (data: Figure) => chart.rerender(<Chart figure={data} />),
    resetValue: () => resetValue?.(),
  };
}

function moveCamera(scene = "scene") {
  const event: Plotly.PlotRelayoutEvent & Record<string, unknown> = {
    [`${scene}.camera`]: movedCamera,
  };
  act(() => plotProps?.onRelayout?.(event));
}

describe("Plotly camera persistence", () => {
  it("keeps the camera when a notebook rerun resets the widget value", async () => {
    const chart = mountChart(figure());
    await waitFor(() => expect(plotProps).toBeDefined());
    moveCamera();
    act(() => chart.resetValue());
    const next = figure();
    next.data = [
      {
        type: "surface",
        z: [
          [5, 6],
          [7, 8],
        ],
      },
    ];
    chart.update(next);
    await waitFor(() =>
      expect(plotProps?.layout.scene?.camera).toEqual(movedCamera),
    );
  });
  it("treats an explicit default scene as the same trace destination", async () => {
    const chart = mountChart(figure());
    await waitFor(() => expect(plotProps).toBeDefined());
    moveCamera();
    chart.unmount();
    const next = figure();
    const surface: Plotly.Data & { scene: string } = {
      type: "surface",
      scene: "scene",
      z: [
        [5, 6],
        [7, 8],
      ],
    };
    next.data = [surface];
    mountChart(next, chart.getValue());
    await waitFor(() =>
      expect(plotProps?.layout.scene?.camera).toEqual(movedCamera),
    );
  });
  it("restores the camera after remounting a chart with the same uirevision", async () => {
    const chart = mountChart(figure());
    await waitFor(() => expect(plotProps).toBeDefined());
    moveCamera();
    chart.unmount();

    const next = figure();
    next.data = [
      {
        type: "surface",
        z: [
          [5, 6],
          [7, 8],
        ],
      },
    ];
    mountChart(next, chart.getValue());
    await waitFor(() =>
      expect(plotProps?.layout.scene?.camera).toEqual(movedCamera),
    );
  });

  it.each([
    "changed revision",
    "no revision",
    "changed camera",
    "incompatible traces",
  ])("uses the figure's camera after remounting with %s", async (change) => {
    const chart = mountChart(figure());
    await waitFor(() => expect(plotProps).toBeDefined());
    moveCamera();
    chart.unmount();
    const next = figure();
    const expected = { eye: { x: -1, y: 0, z: 2 } };
    if (change === "changed revision") {
      next.layout.uirevision = "new-chart";
    } else if (change === "no revision") {
      next.layout.uirevision = undefined;
    } else if (change === "changed camera") {
      next.layout.scene = { camera: expected };
    } else {
      next.data = [{ type: "scatter3d" }];
    }
    mountChart(next, chart.getValue());
    await waitFor(() =>
      expect(plotProps?.layout.scene?.camera).toEqual(
        change === "changed camera" ? expected : initialCamera,
      ),
    );
  });

  it("keeps new scene settings when the figure updates without remounting", async () => {
    const chart = mountChart(figure());
    await waitFor(() => expect(plotProps).toBeDefined());
    moveCamera();
    const next = figure();
    next.layout.scene = { camera: initialCamera, aspectmode: "cube" };
    chart.update(next);
    await waitFor(() =>
      expect(plotProps?.layout.scene).toEqual({
        camera: movedCamera,
        aspectmode: "cube",
      }),
    );
  });

  it("camera events leave the plot data and persisted axis settings intact", async () => {
    const axes = { xaxis: { range: [1, 5] }, yaxis: { range: [2, 6] } };
    mountChart(figure(), axes);
    await waitFor(() => expect(plotProps).toBeDefined());
    const data = plotProps?.data;
    moveCamera();
    expect(plotProps?.data).toBe(data);
    expect(plotProps?.layout.xaxis).toEqual(axes.xaxis);
    expect(plotProps?.layout.yaxis).toEqual(axes.yaxis);
  });

  it("merges partial camera relayout events before restoring the camera", async () => {
    const chart = mountChart(figure());
    await waitFor(() => expect(plotProps).toBeDefined());
    moveCamera();
    const event: Plotly.PlotRelayoutEvent & Record<string, unknown> = {
      "scene.camera.eye.x": 4,
      "scene.camera.up": { x: 0, y: 0, z: 1 },
    };
    act(() => plotProps?.onRelayout?.(event));
    chart.unmount();
    mountChart(figure(), chart.getValue());
    await waitFor(() =>
      expect(plotProps?.layout.scene?.camera).toEqual({
        eye: { x: 4, y: -1, z: 0.5 },
        up: { x: 0, y: 0, z: 1 },
      }),
    );
  });

  it("preserves all partial updates from a single React batch", async () => {
    const chart = mountChart(figure());
    await waitFor(() => expect(plotProps).toBeDefined());
    const x: Plotly.PlotRelayoutEvent & Record<string, unknown> = {
      "scene.camera.eye.x": 4,
    };
    const y: Plotly.PlotRelayoutEvent & Record<string, unknown> = {
      "scene.camera.eye.y": 5,
    };
    act(() => {
      plotProps?.onRelayout?.(x);
      plotProps?.onRelayout?.(y);
    });
    chart.unmount();
    mountChart(figure(), chart.getValue());
    await waitFor(() =>
      expect(plotProps?.layout.scene?.camera).toEqual({
        eye: { x: 4, y: 5, z: 1 },
      }),
    );
  });

  it("restored scene layout does not share nested objects with the input figure", async () => {
    const data = figure();
    data.layout.scene = { camera: initialCamera, xaxis: { range: [0, 10] } };
    mountChart(data);
    await waitFor(() => expect(plotProps).toBeDefined());
    moveCamera();
    await waitFor(() =>
      expect(plotProps?.layout.scene?.camera).toEqual(movedCamera),
    );
    const axis = plotProps?.layout.scene?.xaxis;
    if (!axis?.range) {
      throw new Error("Missing restored scene axis");
    }
    axis.range[0] = 999;
    expect(data.layout.scene.xaxis?.range).toEqual([0, 10]);
  });

  it.each(["revision", "configured camera", "trace type"])(
    "partial events do not reuse stale camera coordinates after a changed %s",
    async (change) => {
      const chart = mountChart(figure());
      await waitFor(() => expect(plotProps).toBeDefined());
      moveCamera();
      const next = figure();
      if (change === "revision") {
        next.layout.uirevision = "new-camera";
      } else if (change === "configured camera") {
        next.layout.scene = { camera: { eye: { x: -2, y: 3, z: 4 } } };
      } else {
        next.data = [{ type: "scatter3d" }];
      }
      chart.update(next);
      await waitFor(() =>
        expect(plotProps?.layout.scene?.camera).toEqual(
          next.layout.scene?.camera,
        ),
      );
      const event: Plotly.PlotRelayoutEvent & Record<string, unknown> = {
        "scene.camera.eye.x": 4,
      };
      act(() => plotProps?.onRelayout?.(event));
      chart.unmount();
      mountChart(next, chart.getValue());
      await waitFor(() =>
        expect(plotProps?.layout.scene?.camera).toEqual({
          eye: {
            x: 4,
            y: change === "configured camera" ? 3 : 1,
            z: change === "configured camera" ? 4 : 1,
          },
        }),
      );
    },
  );

  it.each([0, ""])(
    "a falsy scene revision %s disables persistence",
    async (revision) => {
      const data = figure();
      const scene = { camera: initialCamera, uirevision: revision };
      data.layout.scene = scene;
      const chart = mountChart(data);
      await waitFor(() => expect(plotProps).toBeDefined());
      moveCamera();
      expect(chart.getValue()).toBeUndefined();
      chart.unmount();
      mountChart(data, chart.getValue());
      await waitFor(() =>
        expect(plotProps?.layout.scene?.camera).toEqual(initialCamera),
      );
    },
  );

  it("honors independent revisions for multiple scenes", async () => {
    const data = figure();
    const scene2 = { camera: initialCamera, uirevision: "second-scene" };
    data.layout.scene2 = scene2;
    const chart = mountChart(data);
    await waitFor(() => expect(plotProps).toBeDefined());
    moveCamera();
    moveCamera("scene2");
    chart.unmount();
    const next = figure("changed-global");
    next.layout.scene2 = scene2;
    mountChart(next, chart.getValue());
    await waitFor(() => {
      expect(plotProps?.layout.scene?.camera).toEqual(initialCamera);
      expect(plotProps?.layout.scene2?.camera).toEqual(movedCamera);
    });
  });

  it("reset restores the configured camera and clears its persisted state", async () => {
    const chart = mountChart(figure());
    await waitFor(() => expect(plotProps).toBeDefined());
    moveCamera();
    const buttons = plotProps?.config?.modeBarButtonsToAdd;
    if (!Array.isArray(buttons)) {
      throw new Error("Missing mode bar buttons");
    }
    const reset = buttons.find(
      (button) => typeof button === "object" && button.name === "reset",
    );
    if (typeof reset !== "object") {
      throw new Error("Missing reset button");
    }
    act(() => Reflect.apply(reset.click, undefined, []));
    await waitFor(() =>
      expect(plotProps?.layout.scene?.camera).toEqual(initialCamera),
    );
    expect(chart.getValue()).toEqual({});
  });
});
