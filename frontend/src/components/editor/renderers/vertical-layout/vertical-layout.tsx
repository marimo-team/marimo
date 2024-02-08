/* Copyright 2024 Marimo. All rights reserved. */
import React, { memo, useRef, useState } from "react";
import { CellConfig, CellRuntimeState } from "@/core/cells/types";
import { CellId, HTMLCellId } from "@/core/cells/ids";
import { OutputArea } from "@/components/editor/Output";
import { ICellRendererPlugin, ICellRendererProps } from "../types";
import { VerticalLayoutWrapper } from "./vertical-layout-wrapper";
import { z } from "zod";
import { useDelayVisibility } from "./useDelayVisibility";
import { AppMode } from "@/core/mode";
import { ReadonlyPythonCode } from "@/components/editor/code/readonly-python-code";
import { Code2Icon } from "lucide-react";
import { cn } from "@/utils/cn";
import { Button } from "@/components/ui/button";
import { outputIsStale } from "@/core/cells/cell";
import { isStaticNotebook } from "@/core/static/static-state";

type VerticalLayout = null;
type VerticalLayoutProps = ICellRendererProps<VerticalLayout>;

const VerticalLayoutRenderer: React.FC<VerticalLayoutProps> = ({
  cells,
  appConfig,
  mode,
}) => {
  const { invisible } = useDelayVisibility(cells.length, mode);
  const [showCode, setShowCode] = useState(() => {
    // Default to showing code if the notebook is static
    return isStaticNotebook();
  });
  // Show code if there is at least one cell with code
  const canShowCode = mode === "read" && cells.some((cell) => cell.code);
  return (
    <VerticalLayoutWrapper invisible={invisible} appConfig={appConfig}>
      {cells.map((cell) => (
        <VerticalCell
          key={cell.id}
          cellId={cell.id}
          output={cell.output}
          status={cell.status}
          code={cell.code}
          config={cell.config}
          stopped={cell.stopped}
          showCode={showCode && canShowCode}
          errored={cell.errored}
          mode={mode}
          runStartTimestamp={cell.runStartTimestamp}
          interrupted={cell.interrupted}
        />
      ))}
      {canShowCode && (
        <div
          className={cn(
            "right-0 top-0 z-10 m-4",
            // If the notebook is static, we have a banner at the top, so
            // we can't use fixed positioning. Ideally this is sticky, but the
            // current dom structure makes that difficult.
            isStaticNotebook() ? "absolute" : "fixed",
          )}
        >
          <Button
            variant="secondary"
            onClick={() => setShowCode((prev) => !prev)}
            data-testid="show-code"
          >
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
    | "output"
    | "status"
    | "stopped"
    | "errored"
    | "interrupted"
    | "runStartTimestamp"
  > {
  cellId: CellId;
  config: CellConfig;
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
    config,
    interrupted,
    runStartTimestamp,
    code,
    showCode,
    mode,
  }: VerticalCellProps) => {
    const cellRef = useRef<HTMLDivElement>(null);

    const outputStale = outputIsStale(
      {
        status,
        output,
        interrupted,
        runStartTimestamp,
      },
      false,
    );

    const className = cn("Cell", "hover-actions-parent", {
      published: !showCode,
      interactive: mode === "edit",
      "has-error": errored,
      stopped: stopped,
    });

    const HTMLId = HTMLCellId.create(cellId);
    const hidden = errored || interrupted || stopped;

    // Read mode and show code
    if (mode === "read" && showCode) {
      return (
        <div tabIndex={-1} id={HTMLId} ref={cellRef} className={className}>
          <OutputArea
            allowExpand={true}
            output={output}
            className="output-area"
            cellId={cellId}
            stale={outputStale}
          />
          <div className="tray">
            <ReadonlyPythonCode
              initiallyHideCode={config.hide_code}
              code={code}
            />
          </div>
        </div>
      );
    }

    return hidden ? null : (
      <div tabIndex={-1} id={HTMLId} ref={cellRef} className={className}>
        <OutputArea
          allowExpand={mode === "edit"}
          output={output}
          className="output-area"
          cellId={cellId}
          stale={outputStale}
        />
      </div>
    );
  },
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
