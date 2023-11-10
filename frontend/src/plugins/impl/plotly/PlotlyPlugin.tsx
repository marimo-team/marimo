/* Copyright 2023 Marimo. All rights reserved. */
import { z } from "zod";

import { IPlugin, IPluginProps } from "@/plugins/types";

import Plot, { Figure } from "react-plotly.js";
import { Logger } from "@/utils/Logger";

import "./plotly.css";
import { Objects } from "@/utils/objects";
import { memo, useMemo } from "react";
import useEvent from "react-use-event-hook";

interface Data {
  figure: Figure;
}

type AxisName = string;
type AxisDatum = unknown;

type T =
  | {
      points?: Array<Record<AxisName, AxisDatum>>;
      range?: {
        x?: number[];
        y?: number[];
      };
    }
  | undefined;

export class PlotlyPlugin implements IPlugin<T, Data> {
  tagName = "marimo-plotly";

  validator = z.object({
    figure: z
      .object({})
      .passthrough()
      .transform((spec) => spec as unknown as Figure),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    return (
      <PlotlyComponent
        {...props.data}
        host={props.host}
        value={props.value}
        setValue={props.setValue}
      />
    );
  }
}

interface PlotlyPluginProps extends Data {
  value: T;
  setValue: (value: T) => void;
  host: HTMLElement;
}

const config = {
  displaylogo: false,
};

export const PlotlyComponent = memo(
  ({ figure, setValue }: PlotlyPluginProps) => {
    const layout: Partial<Plotly.Layout> = useMemo(() => {
      // Enable autosize if width is not specified
      const shouldAutoSize = figure.layout.width === undefined;
      return {
        autosize: shouldAutoSize,
        dragmode: "select",
        height: 560,
        // Prioritize user's config
        ...figure.layout,
      };
    }, [figure.layout]);

    return (
      <Plot
        {...figure}
        layout={layout}
        config={config}
        onSelected={useEvent((evt) => {
          setValue({
            points: extractPoints(evt.points),
            range: evt.range,
          });
        })}
        className="w-full h-full"
        useResizeHandler={true}
        frames={figure.frames ?? undefined}
        onError={useEvent((err) => {
          Logger.error("PlotlyPlugin: ", err);
        })}
      />
    );
  }
);
PlotlyComponent.displayName = "PlotlyComponent";

const keysToInclude = new Set(["x", "y", "value", "label"]);
function extractPoints(
  points: Plotly.PlotDatum[]
): Array<Record<AxisName, AxisDatum>> {
  if (!points) {
    return [];
  }

  return points.map((point) => {
    const data: Record<AxisName, AxisDatum> = Objects.filter(point, (_v, key) =>
      keysToInclude.has(key)
    );
    // Add name if it exists
    if (point.data.name) {
      data.name = point.data.name;
    }
    return data;
  });
}
