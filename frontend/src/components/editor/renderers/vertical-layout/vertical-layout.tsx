/* Copyright 2023 Marimo. All rights reserved. */
import { memo, useRef } from "react";
import { CellRuntimeState } from "@/core/cells/types";
import { CellId, HTMLCellId } from "@/core/cells/ids";
import { OutputArea } from "@/components/editor/Output";
import clsx from "clsx";
import { ICellRendererPlugin, ICellRendererProps } from "../types";
import { VerticalLayoutWrapper } from "./vertical-layout-wrapper";
import { z } from "zod";
import { useDelayVisibility } from "./useDelayVisiblity";
import { AppMode } from "@/core/mode";

type VerticalLayout = null;
type VerticalLayoutProps = ICellRendererProps<VerticalLayout>;

const VerticalLayoutRenderer: React.FC<VerticalLayoutProps> = ({
  cells,
  appConfig,
  mode,
}) => {
  const { invisible } = useDelayVisibility(cells.length, mode);
  return (
    <VerticalLayoutWrapper
      className="sm:pt-8"
      invisible={invisible}
      appConfig={appConfig}
    >
      {cells.map((cell) => (
        <VerticalCell
          key={cell.id}
          cellId={cell.id}
          output={cell.output}
          status={cell.status}
          stopped={cell.stopped}
          errored={cell.errored}
          mode={mode}
          interrupted={cell.interrupted}
        />
      ))}
    </VerticalLayoutWrapper>
  );
};

interface VerticalCellProps
  extends Pick<
    CellRuntimeState,
    "output" | "status" | "stopped" | "errored" | "interrupted"
  > {
  cellId: CellId;
  mode: AppMode;
}

const VerticalCell = memo(
  ({
    output,
    cellId,
    status,
    stopped,
    errored,
    interrupted,
    mode,
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
          allowExpand={mode === "edit"}
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
