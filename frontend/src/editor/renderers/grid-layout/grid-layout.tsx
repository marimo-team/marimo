/* Copyright 2023 Marimo. All rights reserved. */
import React, { memo } from "react";
import { Responsive, WidthProvider } from "react-grid-layout";
import { ICellRendererPlugin, ICellRendererProps } from "../types";
import {
  GridLayout,
  SerializedGridLayout,
  SerializedGridLayoutCell,
} from "./types";
import { OutputArea } from "@/editor/Output";
import { CellState } from "@/core/model/cells";

import "react-grid-layout/css/styles.css";
import "./styles.css";
import { Logger } from "@/utils/Logger";
import { z } from "zod";
import { Maps } from "@/utils/maps";
import { CellId } from "@/core/model/ids";
import { AppMode } from "@/core/mode";
import { TinyCode } from "@/editor/cell/TinyCode";
import { cn } from "@/lib/utils";
import { XIcon } from "lucide-react";

type Props = ICellRendererProps<GridLayout>;

const ReactGridLayout = WidthProvider(Responsive);

const cols = {
  // we only allow 1 responsive breakpoint
  // we can change this later if we want to support more,
  // but this increases complexity to the user
  lg: 12,
};

const GridLayoutRenderer: React.FC<Props> = ({
  layout,
  setLayout,
  cells,
  mode,
}) => {
  const isReading = mode === "read";
  const [isDragging, setIsDragging] = React.useState(false);
  const inGridIds = new Set(layout.cells.map((cell) => cell.i));
  const [droppingItem, setDroppingItem] = React.useState<{
    i: string;
    w?: number;
    h?: number;
  } | null>(null);

  const grid = (
    <ReactGridLayout
      breakpoint="lg"
      layouts={{
        lg: layout.cells,
      }}
      cols={cols}
      isBounded={true}
      allowOverlap={false}
      autoSize={true}
      className={cn(
        !isReading && "min-w-[800px] min-h-[600px]",
        isReading && "disable-animation"
      )}
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
        setIsDragging(false);
        if (!dropped) {
          return;
        }
        setLayout({
          ...layout,
          cells: [...cellLayouts, dropped],
        });
      }}
      onDragStart={() => setIsDragging(true)}
      onDragStop={() => setIsDragging(false)}
      // When in read mode, disable dragging and resizing
      isDraggable={!isReading}
      isDroppable={!isReading}
      isResizable={!isReading}
    >
      {cells
        .filter((cell) => inGridIds.has(cell.key))
        .map((cell) => (
          <div
            key={cell.key}
            className={cn(
              "relative transparent-when-disconnected",
              !isReading &&
              "hover:bg-[var(--sage-2)] border-transparent hover:border-border border hover:rounded hover-actions-parent",
              isDragging && "bg-[var(--sage-2)] border-border rounded",
              "overflow-hidden p-2"
            )}
          >
            <GridCell
              code={cell.code}
              mode={mode}
              cellKey={cell.key}
              output={cell.output}
              status={cell.status}
            />
            {!isReading && (
              <div className="absolute top-0 right-0 p-1 hover-action">
                <XIcon
                  className="cursor-pointer h-4 w-4 opacity-60 hover:opacity-100"
                  onClick={() => {
                    setLayout({
                      ...layout,
                      cells: layout.cells.filter((c) => c.i !== cell.key),
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

  const notInGrid = cells.filter((cell) => !inGridIds.has(cell.key));

  return (
    <div className={cn("flex h-full overflow-hidden gap-2 px-2 pb-2")}>
      <div className="flex-grow overflow-auto border rounded bg-[var(--sage-1)] shadow-sm transparent-when-disconnected">
        {grid}
      </div>
      <div className="flex-none flex flex-col w-[400px] p-3 gap-3 overflow-auto h-full bg-[var(--sage-3)] border rounded shadow-sm transparent-when-disconnected">
        <div className="text font-bold text-[var(--sage-10)] overflow-auto flex-shrink-0">
          Outputs
        </div>
        {notInGrid.map((cell) => (
          <div
            key={cell.key}
            draggable={true}
            unselectable="on"
            data-cell-id={cell.key}
            // Firefox requires some kind of initialization which we can do by adding this attribute
            // @see https://bugzilla.mozilla.org/show_bug.cgi?id=568313
            onDragStart={(e) => {
              // get height of self
              const height = e.currentTarget.offsetHeight;

              setDroppingItem({
                i: cell.key,
                w: 3,
                h: Math.ceil(height / layout.rowHeight) || 1,
              });
              e.dataTransfer.setData("text/plain", "");
            }}
            className="droppable-element bg-[var(--sage-2)] border-border border overflow-hidden p-2 rounded flex-shrink-0"
          >
            <GridCell
              code={cell.code}
              mode={mode}
              cellKey={cell.key}
              output={cell.output}
              status={cell.status}
            />
          </div>
        ))}
      </div>
    </div>
  );
};

interface GridCellProps extends Pick<CellState, "output" | "status" | "code"> {
  cellKey: CellId;
  mode: AppMode;
}

const GridCell = memo(
  ({ output, cellKey, status, mode, code }: GridCellProps) => {
    const loading = status === "running" || status === "queued";

    const isOutputEmpty = output == null || output.data === "";
    // If not reading, show code when there is no output
    if (isOutputEmpty && mode !== "read") {
      return <TinyCode code={code} />;
    }

    return (
      <div>
        <OutputArea output={output} cellId={cellKey} stale={loading} />
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
    columns: z.number().min(1).max(12),
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
          i: cell.key,
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
      const layout = layoutsByKey.get(cell.key);
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
    columns: 12,
    rowHeight: 40,
    cells: [],
  }),
};
