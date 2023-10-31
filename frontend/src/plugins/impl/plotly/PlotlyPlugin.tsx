/* Copyright 2023 Marimo. All rights reserved. */
import { z } from "zod";

import { IPluginProps } from "@/plugins/types";

import Plot, { Figure } from "react-plotly.js";
import { IStatelessPlugin } from "@/plugins/stateless-plugin";
import { T } from "vitest/dist/reporters-5f784f42";
import { Logger } from "@/utils/Logger";

import "./plotly.css";

interface Data {
  figure: Figure;
}

export class PlotlyPlugin implements IStatelessPlugin<Data> {
  tagName = "marimo-plotly";

  validator = z.object({
    figure: z
      .object({})
      .passthrough()
      .transform((spec) => spec as unknown as Figure),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    return <PlotlyComponent {...props.data} host={props.host} />;
  }
}

interface PlotlyPluginProps extends Data {
  host: HTMLElement;
}

export const PlotlyComponent = ({ figure, host }: PlotlyPluginProps) => {
  // Enable autosize if width is not specified
  const shouldAutoSize = figure.layout.width === undefined;
  return (
    <Plot
      {...figure}
      layout={{
        autosize: shouldAutoSize,
        // Prioritize user's config
        ...figure.layout,
      }}
      config={{
        displaylogo: false,
      }}
      className="w-full h-full"
      useResizeHandler={true}
      frames={figure.frames ?? undefined}
      onError={(err) => {
        Logger.error("PlotlyPlugin: ", err);
      }}
    />
  );
};
