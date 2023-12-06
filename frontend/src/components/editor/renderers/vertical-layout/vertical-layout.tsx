/* Copyright 2023 Marimo. All rights reserved. */
import { memo, useRef, useState } from "react";
import { CellRuntimeState } from "@/core/cells/types";
import { CellId, HTMLCellId } from "@/core/cells/ids";
import { OutputArea } from "@/components/editor/Output";
import clsx from "clsx";
import { ICellRendererPlugin, ICellRendererProps } from "../types";
import { VerticalLayoutWrapper } from "./vertical-layout-wrapper";
import { z } from "zod";
import { useDelayVisibility } from "./useDelayVisiblity";
import { AppMode } from "@/core/mode";
import { ReadonlyPythonCode } from "@/components/editor/code/readonly-python-code";
import { Button } from "../../inputs/Inputs";
import { Code2Icon } from "lucide-react";
import { isStaticNotebook } from "@/core/static/static-state";

type VerticalLayout = null;
type VerticalLayoutProps = ICellRendererProps<VerticalLayout>;

const VerticalLayoutRenderer: React.FC<VerticalLayoutProps> = ({
  cells,
  appConfig,
  mode,
}) => {
  const { invisible } = useDelayVisibility(cells.length, mode);
  const [showCode, setShowCode] = useState(false);
  const canShowCode = mode === "read" && isStaticNotebook();
  return (
    <VerticalLayoutWrapper invisible={invisible} appConfig={appConfig}>
      {cells.map((cell) => (
        <VerticalCell
          key={cell.id}
          cellId={cell.id}
          output={cell.output}
          status={cell.status}
          code={cell.code}
          stopped={cell.stopped}
          showCode={showCode && canShowCode}
          errored={cell.errored}
          mode={mode}
          interrupted={cell.interrupted}
        />
      ))}
      {canShowCode && (
        <div className="fixed m-4 left-0 bottom-0">
          <Button onClick={() => setShowCode((prev) => !prev)}>
            <Code2Icon className="w-4 h-4 mr-2" />
            {showCode ? "Hide code" : "Show code"}
          </Button>
        </div>
      )}
    </VerticalLayoutWrapper>
  );
};

interface VerticalCellProps
  extends Pick<
    CellRuntimeState,
    "output" | "status" | "stopped" | "errored" | "interrupted"
  > {
  cellId: CellId;
  code: string;
  mode: AppMode;
  showCode: boolean;
}

const VerticalCell = memo(
  ({
    output,
    cellId,
    status,
    stopped,
    errored,
    interrupted,
    code,
    showCode,
    mode,
  }: VerticalCellProps) => {
    const cellRef = useRef<HTMLDivElement>(null);
    const loading = status === "running" || status === "queued";

    const className = clsx("Cell", "hover-actions-parent", {
      published: true,
      "has-error": errored,
      stopped: stopped,
      "flex flex-col": showCode && code,
    });

    const HTMLId = HTMLCellId.create(cellId);
    const hidden = errored || interrupted || stopped;

    return hidden ? null : (
      <div tabIndex={-1} id={HTMLId} ref={cellRef} className={className}>
        {showCode && code && (
          <div className="shadow-sm border rounded overflow-hidden mt-4 mb-2">
            <ReadonlyPythonCode code={code} />
          </div>
        )}
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
