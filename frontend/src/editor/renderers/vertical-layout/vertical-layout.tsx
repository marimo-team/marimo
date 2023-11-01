/* Copyright 2023 Marimo. All rights reserved. */
import { memo, useRef } from "react";
import { CellRuntimeState } from "@/core/model/cells";
import { CellId, HTMLCellId } from "@/core/model/ids";
import { OutputArea } from "@/editor/Output";
import clsx from "clsx";
import { ICellRendererPlugin, ICellRendererProps } from "../types";
import { VerticalLayoutWrapper } from "./vertical-layout-wrapper";
import { z } from "zod";
import { useDelayVisibility } from "./useDelayVisiblity";

type VerticalLayout = null;
type VerticalLayoutProps = ICellRendererProps<VerticalLayout>;

const VerticalLayoutRenderer: React.FC<VerticalLayoutProps> = ({
  cells,
  appConfig,
  mode,
}) => {
  const { invisible } = useDelayVisibility(cells, mode);
  return (
    <VerticalLayoutWrapper invisible={invisible} appConfig={appConfig}>
      {cells.map((cell) => (
        <VerticalCell
          key={cell.key}
          cellId={cell.key}
          output={cell.output}
          status={cell.status}
          stopped={cell.stopped}
          errored={cell.errored}
          interrupted={cell.interrupted}
        />
      ))}
    </VerticalLayoutWrapper>
  );
};

interface VerticalCellProps
  extends Pick<
    CellRuntimeState,
    "output" | "key" | "status" | "stopped" | "errored" | "interrupted"
  > {
  cellId: CellId;
}

const VerticalCell = memo(
  ({
    output,
    cellId,
    status,
    stopped,
    errored,
    interrupted,
  }: VerticalCellProps) => {
    const cellRef = useRef<HTMLDivElement>(null);
    const loading = status === "running" || status === "queued";

    const className = clsx("Cell", "hover-actions-parent", {
      published: true,
      "has-error": errored,
      stopped: stopped,
    });

    const HTMLId = HTMLCellId.create(cellId);
    const hidden = errored || interrupted || stopped;
    return hidden ? null : (
      <div tabIndex={-1} id={HTMLId} ref={cellRef} className={className}>
        <OutputArea
          output={output}
          className="output-area"
          cellId={cellId}
          stale={loading && !interrupted}
        />
      </div>
    );
  }
);
VerticalCell.displayName = "VerticalCell";

export const VerticalLayoutPlugin: ICellRendererPlugin<
  VerticalLayout,
  VerticalLayout
> = {
  type: "vertical",
  name: "Vertical",
  validator: z.any(),
  Component: VerticalLayoutRenderer,
  deserializeLayout: (serialized) => serialized,
  serializeLayout: (layout) => layout,
  getInitialLayout: () => null,
};
