/* Copyright 2023 Marimo. All rights reserved. */
import React, { memo, useMemo, useState } from "react";
import { Responsive, WidthProvider } from "react-grid-layout";
import { ICellRendererPlugin, ICellRendererProps } from "../types";
import {
  GridLayout,
  SerializedGridLayout,
  SerializedGridLayoutCell,
} from "./types";
import { OutputArea } from "@/editor/Output";
import { CellRuntimeState } from "@/core/model/cells";

import "react-grid-layout/css/styles.css";
import "./styles.css";
import { Logger } from "@/utils/Logger";
import { z } from "zod";
import { Maps } from "@/utils/maps";
import { CellId } from "@/core/model/ids";
import { AppMode } from "@/core/mode";
import { TinyCode } from "@/editor/cell/TinyCode";
import { cn } from "@/lib/utils";
import { LockIcon, XIcon } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useIsDragging } from "@/hooks/useIsDragging";
import { Switch } from "@/components/ui/switch";

type Props = ICellRendererProps<GridLayout>;

const ReactGridLayout = WidthProvider(Responsive);

const MARGIN: [number, number] = [0, 0];

const GridLayoutRenderer: React.FC<Props> = ({
  layout,
  setLayout,
  cells,
  mode,
}) => {
  const isReading = mode === "read";
  const inGridIds = new Set(layout.cells.map((cell) => cell.i));
  const [droppingItem, setDroppingItem] = useState<{
    i: string;
    w?: number;
    h?: number;
  } | null>(null);
  const [isLocked, setIsLocked] = useState(false);

  const cols = useMemo(
    () => ({
      // we only allow 1 responsive breakpoint
      // we can change this later if we want to support more,
      // but this increases complexity to the user
      lg: layout.columns,
    }),
    [layout.columns]
  );

  const { isDragging, ...dragProps } = useIsDragging();

  const enableInteractions = !isReading && !isLocked;

  const grid = (
    <ReactGridLayout
      breakpoint="lg"
      layouts={{
        lg: layout.cells,
      }}
      cols={cols}
      isBounded={true}
      allowOverlap={false}
      className={cn(
        !isReading && "min-w-[800px] min-h-full",
        isReading && "disable-animation"
      )}
      margin={MARGIN}
      compactType={null}
      preventCollision={true}
      rowHeight={layout.rowHeight}
      onLayoutChange={(cellLayouts) =>
        setLayout({
          ...layout,
          cells: cellLayouts,
        })
      }
      droppingItem={
        droppingItem
          ? {
              i: droppingItem.i,
              w: droppingItem.w || 2,
              h: droppingItem.h || 2,
            }
          : undefined
      }
      onDrop={(cellLayouts, dropped, _event) => {
        dragProps.onDragStop();
        if (!dropped) {
          return;
        }
        setLayout({
          ...layout,
          cells: [...cellLayouts, dropped],
        });
      }}
      onDragStart={(_layout, _oldItem, _newItem, _placeholder, event) => {
        dragProps.onDragStart(event);
      }}
      onDrag={(_layout, _oldItem, _newItem, _placeholder, event) => {
        dragProps.onDragMove(event);
      }}
      onDragStop={() => {
        dragProps.onDragStop();
      }}
      onResizeStop={() => {
        // Dispatch a resize event so widgets know to resize
        window.dispatchEvent(new Event("resize"));
      }}
      // When in read mode or locked, disable dragging and resizing
      isDraggable={enableInteractions}
      isDroppable={enableInteractions}
      isResizable={enableInteractions}
      draggableHandle={enableInteractions ? undefined : "noop"}
    >
      {cells
        .filter((cell) => inGridIds.has(cell.id))
        .map((cell) => (
          <div
            key={cell.id}
            className={cn(
              "relative transparent-when-disconnected z-10",
              enableInteractions &&
                "bg-background hover:bg-[var(--slate-2)] border-transparent hover:border-border border hover:rounded hover-actions-parent",
              isDragging && "bg-[var(--slate-2)] border-border rounded"
            )}
          >
            <GridCell
              code={cell.code}
              mode={mode}
              cellId={cell.id}
              output={cell.output}
              status={cell.status}
              hidden={cell.errored || cell.interrupted || cell.stopped}
            />
            {enableInteractions && (
              <div className="absolute top-0 right-0 p-1 hover-action">
                <XIcon
                  className="cursor-pointer h-4 w-4 opacity-60 hover:opacity-100"
                  onClick={() => {
                    setLayout({
                      ...layout,
                      cells: layout.cells.filter((c) => c.i !== cell.id),
                    });
                  }}
                />
              </div>
            )}
          </div>
        ))}
    </ReactGridLayout>
  );

  if (isReading) {
    return grid;
  }

  const notInGrid = cells.filter((cell) => !inGridIds.has(cell.id));

  return (
    <>
      <div className="flex flex-row absolute left-5 top-4 gap-4">
        <div className="flex flex-row items-center gap-2">
          <Label htmlFor="columns">Columns</Label>
          <Input
            id="columns"
            type="number"
            value={layout.columns}
            className="w-[60px]"
            placeholder="# of Columns"
            min={1}
            onChange={(e) => {
              setLayout({
                ...layout,
                columns: Number.parseInt(e.target.value) || 1,
              });
            }}
          />
        </div>
        <div className="flex flex-row items-center gap-2">
          <Label htmlFor="rowHeight">Row Height (px)</Label>
          <Input
            id="rowHeight"
            type="number"
            value={layout.rowHeight}
            className="w-[60px]"
            placeholder="Row Height (px)"
            min={1}
            onChange={(e) => {
              setLayout({
                ...layout,
                rowHeight: Number.parseInt(e.target.value) || 1,
              });
            }}
          />
        </div>
        <div className="flex flex-row items-center gap-2">
          <Label className="flex flex-row items-center gap-1" htmlFor="lock">
            <LockIcon className="h-3 w-3" />
            Lock Grid
          </Label>
          <Switch
            id="lock"
            checked={isLocked}
            size="sm"
            onCheckedChange={setIsLocked}
          />
        </div>
      </div>
      <div
        className={cn("relative flex h-full overflow-hidden gap-2 px-2 pb-2")}
      >
        <div
          className={cn(
            "flex-grow overflow-auto border rounded bg-[var(--slate-2)] shadow-sm transparent-when-disconnected",
            !enableInteractions && "bg-background"
          )}
          style={
            enableInteractions
              ? {
                  backgroundImage:
                    "repeating-linear-gradient(var(--gray-4) 0 1px, transparent 1px 100%), repeating-linear-gradient(90deg, var(--gray-4) 0 1px, transparent 1px 100%)",
                  backgroundSize: `calc((100% / ${layout.columns})) ${layout.rowHeight}px`,
                }
              : undefined
          }
        >
          {grid}
        </div>
        <div className="flex-none flex flex-col w-[400px] p-3 gap-3 overflow-auto h-full bg-[var(--slate-2)] border rounded shadow-sm transparent-when-disconnected">
          <div className="text font-bold text-[var(--slate-20)] overflow-auto flex-shrink-0">
            Outputs
          </div>
          {notInGrid.map((cell) => (
            <div
              key={cell.id}
              draggable={true}
              unselectable="on"
              data-cell-id={cell.id}
              // Firefox requires some kind of initialization which we can do by adding this attribute
              // @see https://bugzilla.mozilla.org/show_bug.cgi?id=568313
              onDragStart={(e) => {
                // get height of self
                const height = e.currentTarget.offsetHeight;

                setDroppingItem({
                  i: cell.id,
                  w: layout.columns / 4,
                  h: Math.ceil(height / layout.rowHeight) || 1,
                });
                e.dataTransfer.setData("text/plain", "");
              }}
              className="droppable-element bg-background border-border border overflow-hidden p-2 rounded flex-shrink-0"
            >
              <GridCell
                code={cell.code}
                mode={mode}
                cellId={cell.id}
                output={cell.output}
                status={cell.status}
                hidden={false}
              />
            </div>
          ))}
        </div>
      </div>
    </>
  );
};

interface GridCellProps extends Pick<CellRuntimeState, "output" | "status"> {
  code: string;
  cellId: CellId;
  mode: AppMode;
  hidden: boolean;
}

const GridCell = memo(
  ({ output, cellId, status, mode, code, hidden }: GridCellProps) => {
    const loading = status === "running" || status === "queued";

    const isOutputEmpty = output == null || output.data === "";
    // If not reading, show code when there is no output
    if (isOutputEmpty && mode !== "read") {
      return <TinyCode code={code} />;
    }

    return (
      <div
        className={cn("h-full w-full overflow-auto p-2", hidden && "invisible")}
      >
        <OutputArea output={output} cellId={cellId} stale={loading} />
      </div>
    );
  }
);
GridCell.displayName = "GridCell";

/**
 * Plugin definition for the grid layout.
 */
export const GridLayoutPlugin: ICellRendererPlugin<
  SerializedGridLayout,
  GridLayout
> = {
  type: "grid",
  name: "Grid",

  validator: z.object({
    columns: z.number().min(1),
    rowHeight: z.number().min(1),
    cells: z.array(
      z.object({
        position: z
          .tuple([z.number(), z.number(), z.number(), z.number()])
          .nullable(),
      })
    ),
  }),

  deserializeLayout: (serialized, cells): GridLayout => {
    if (serialized.cells.length === 0) {
      return {
        columns: serialized.columns,
        rowHeight: serialized.rowHeight,
        cells: [],
      };
    }

    if (serialized.cells.length !== cells.length) {
      Logger.warn(
        "Number of cells in layout does not match number of cells in notebook"
      );
    }

    return {
      columns: serialized.columns,
      rowHeight: serialized.rowHeight,
      cells: serialized.cells.flatMap((cellLayout, idx) => {
        const position = cellLayout.position;
        if (!position) {
          return [];
        }
        const cell = cells[idx];
        if (!cell) {
          return [];
        }
        return {
          i: cell.id,
          x: position[0],
          y: position[1],
          w: position[2],
          h: position[3],
        };
      }),
    };
  },

  serializeLayout: (layout, cells): SerializedGridLayout => {
    const layoutsByKey = Maps.keyBy(layout.cells, (cell) => cell.i);
    const serializedCells: SerializedGridLayoutCell[] = cells.map((cell) => {
      const layout = layoutsByKey.get(cell.id);
      if (!layout) {
        return {
          position: null,
        };
      }
      return {
        position: [layout.x, layout.y, layout.w, layout.h],
      };
    });

    return {
      columns: layout.columns,
      rowHeight: layout.rowHeight,
      cells: serializedCells,
    };
  },

  Component: GridLayoutRenderer,

  getInitialLayout: () => ({
    columns: 24,
    rowHeight: 20,
    cells: [],
  }),
};
