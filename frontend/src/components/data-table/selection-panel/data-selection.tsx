/* Copyright 2024 Marimo. All rights reserved. */

import { useResizeHandle } from "@/hooks/useResizeHandle";
import {
  XIcon,
  ChevronLeft,
  ChevronRight,
  SearchIcon,
  ChevronsLeft,
  ChevronsRight,
  Layers2Icon,
} from "lucide-react";
import { useState } from "react";
import { PanelResizeHandle, Panel } from "react-resizable-panels";
import { Button } from "@/components/ui/button";
import { INDEX_COLUMN_NAME, SELECT_COLUMN_ID } from "../types";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Cell } from "@tanstack/react-table";
import { DATA_TYPE_ICON } from "@/components/datasets/icons";
import { Input } from "@/components/ui/input";
import { Tooltip } from "@/components/ui/tooltip";
import { NAMELESS_COLUMN_PREFIX, renderCellValue } from "../columns";
import { handleDragging } from "@/components/editor/chrome/wrapper/utils";
import type { Row } from "@tanstack/react-table";
import { isOverlayAtom } from "./panel-atoms";
import { useAtom } from "jotai";
import { Functions } from "@/utils/functions";
import { CopyClipboardIcon } from "@/components/icons/copy-icon";

export interface DataSelectionPanelProps {
  rows: Array<Row<unknown>>;
  closePanel: () => void;
}

export const DataSelectionPanel: React.FC<DataSelectionPanelProps> = ({
  rows,
  closePanel,
}) => {
  const [isOverlay, setIsOverlay] = useAtom(isOverlayAtom);

  const dataSelection = (
    <DataSelection
      rows={rows}
      closePanel={closePanel}
      isOverlay={isOverlay}
      setIsOverlay={setIsOverlay}
    />
  );

  if (isOverlay) {
    return <ResizableComponent>{dataSelection}</ResizableComponent>;
  }

  return (
    <>
      <PanelResizeHandle
        onDragging={handleDragging}
        className="resize-handle border-border z-20 no-print border-l"
      />
      <Panel defaultSize={25}>{dataSelection}</Panel>
    </>
  );
};

const DataSelection = ({
  rows,
  closePanel,
  isOverlay,
  setIsOverlay,
}: {
  rows: Array<Row<unknown>>;
  closePanel: () => void;
  isOverlay: boolean;
  setIsOverlay: (isOverlay: boolean) => void;
}) => {
  const [selectedRowIdx, setSelectedRowIdx] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");

  const currentRow = rows.at(selectedRowIdx);

  const rowValues: Record<string, Cell<unknown, unknown>> = {};
  const cells = currentRow?.getAllCells() ?? [];
  for (const cell of cells) {
    if (
      cell.column.id === SELECT_COLUMN_ID ||
      cell.column.id === INDEX_COLUMN_NAME
    ) {
      continue;
    }
    if (cell.column.id.startsWith(NAMELESS_COLUMN_PREFIX)) {
      // Leave the column name empty
      cell.column.id = "";
    }
    rowValues[cell.column.id] = cell;
  }

  // Selects the last row if selected row is out of bounds
  if (selectedRowIdx >= rows.length) {
    setSelectedRowIdx(rows.length - 1);
  }

  const searchedRows = filterRows(rowValues, searchQuery);

  const renderModeToggle = () => {
    return (
      <div className="flex flex-row items-center gap-1">
        <Tooltip content={isOverlay ? "Turn off overlay" : "Overlay content"}>
          <Button
            variant={isOverlay ? "link" : "ghost"}
            size="icon"
            onClick={() => setIsOverlay(!isOverlay)}
            aria-label={isOverlay ? "Turn off overlay" : "Overlay content"}
          >
            <Layers2Icon className="w-4 h-4" />
          </Button>
        </Tooltip>
      </div>
    );
  };

  const handleSelectRow = (rowIdx: number) => {
    if (rowIdx < 0 || rowIdx >= rows.length) {
      return;
    }
    setSelectedRowIdx(rowIdx);
  };

  const buttonStyles = "h-6 w-6 p-0.5";

  return (
    <div className="mt-2 pb-7 mb-4 h-full overflow-auto">
      <div className="flex flex-row justify-between items-center mx-2">
        {renderModeToggle()}
        <Button
          variant="linkDestructive"
          size="icon"
          onClick={closePanel}
          aria-label="Close selection panel"
        >
          <XIcon className="w-4 h-4" />
        </Button>
      </div>

      <div className="flex flex-col gap-3 mt-4">
        <div className="flex flex-row gap-2 justify-end items-center mr-2">
          <Button
            variant="outline"
            size="xs"
            className={buttonStyles}
            onClick={() => handleSelectRow(0)}
            disabled={selectedRowIdx === 0}
            aria-label="Go to first row"
          >
            <ChevronsLeft />
          </Button>
          <Button
            variant="outline"
            size="xs"
            className={buttonStyles}
            onClick={() => handleSelectRow(selectedRowIdx - 1)}
            disabled={selectedRowIdx === 0}
            aria-label="Previous row"
          >
            <ChevronLeft />
          </Button>
          <span className="text-xs">
            Row {selectedRowIdx + 1} of {rows.length}
          </span>
          <Button
            variant="outline"
            size="xs"
            className={buttonStyles}
            onClick={() => handleSelectRow(selectedRowIdx + 1)}
            disabled={selectedRowIdx === rows.length - 1}
            aria-label="Next row"
          >
            <ChevronRight />
          </Button>
          <Button
            variant="outline"
            size="xs"
            className={buttonStyles}
            onClick={() => handleSelectRow(rows.length - 1)}
            aria-label="Go to last row"
          >
            <ChevronsRight />
          </Button>
        </div>

        <div className="mx-2 -mb-1">
          <Input
            type="text"
            placeholder="Search"
            onChange={(e) => setSearchQuery(e.target.value)}
            icon={<SearchIcon className="w-4 h-4" />}
            className="mb-0 border-border"
            data-testid="selection-panel-search-input"
          />
        </div>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-1/4">Column</TableHead>
              <TableHead className="w-3/4">Value</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {searchedRows.map(([columnName, cell]) => {
              const Icon =
                DATA_TYPE_ICON[
                  cell.column.columnDef.meta?.dataType || "unknown"
                ];
              const cellContent = renderCellValue(
                cell.column,
                cell.renderValue,
                cell.getValue,
                Functions.NOOP,
                "text-left break-all",
              );

              const cellValue = cell.getValue();
              const cellValueString =
                typeof cellValue === "object"
                  ? JSON.stringify(cellValue)
                  : String(cellValue);

              return (
                <TableRow key={columnName} className="group">
                  <TableCell className="flex flex-row items-center gap-1.5">
                    <Icon className="w-4 h-4 p-0.5 rounded-sm bg-muted" />
                    {columnName}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-row items-center justify-between gap-1">
                      {cellContent}
                      <CopyClipboardIcon
                        value={cellValueString}
                        className="w-3 h-3 mr-1 text-muted-foreground cursor-pointer opacity-0 group-hover:opacity-100"
                      />
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
};

export function filterRows(
  rowValues: Record<string, Cell<unknown, unknown>>,
  searchQuery: string,
) {
  return Object.entries(rowValues).filter(([columnName, cell]) => {
    const colName = columnName.toLowerCase();
    const cellValue = cell.getValue();

    let cellValueString =
      typeof cellValue === "object"
        ? JSON.stringify(cellValue)
        : String(cellValue);
    cellValueString = cellValueString.toLowerCase();
    const searchQueryLower = searchQuery.toLowerCase();

    return (
      colName.includes(searchQueryLower) ||
      cellValueString.includes(searchQueryLower)
    );
  });
}

interface ResizableComponentProps {
  children: React.ReactNode;
}

const ResizableComponent = ({ children }: ResizableComponentProps) => {
  const { resizableDivRef, handleRef, style } = useResizeHandle({
    startingWidth: 400,
    direction: "left",
  });

  return (
    <div className="absolute z-40 right-0 h-full bg-background flex flex-row">
      <div ref={handleRef} className="w-1 h-full cursor-col-resize border-l" />
      <div ref={resizableDivRef} style={style}>
        {children}
      </div>
    </div>
  );
};
