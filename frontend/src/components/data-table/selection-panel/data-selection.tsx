/* Copyright 2024 Marimo. All rights reserved. */

import { useResizeHandle } from "@/hooks/useResizeHandle";
import { useAtom, useAtomValue } from "jotai";
import {
  XIcon,
  ChevronLeft,
  ChevronRight,
  SearchIcon,
  PinIcon,
} from "lucide-react";
import { useState, useMemo } from "react";
import { PanelResizeHandle, Panel } from "react-resizable-panels";
import {
  currentlyFocusedCellAtom,
  selectionPanelOpenAtom,
  tableDataAtom,
} from "./panel-atoms";
import { Button } from "@/components/ui/button";
import { atom } from "jotai";
import { SELECT_COLUMN_ID } from "../types";
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

export const DataSelectionPanel: React.FC<{
  handleDragging: (isDragging: boolean) => void;
}> = ({ handleDragging }) => {
  // If pinned, the right panel
  const [isPinned, setIsPinned] = useState(true);
  const [isOpen, setIsOpen] = useAtom(selectionPanelOpenAtom);
  const currentlyFocusedCell = useAtomValue(currentlyFocusedCellAtom);

  const [selectedRowIdx, setSelectedRowIdx] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");

  // Only get atom value if panel is open
  const tableValues = useAtomValue(
    useMemo(
      () => atom((get) => (isOpen ? get(tableDataAtom) : null)),
      [isOpen],
    ),
  );

  if (!isOpen || !tableValues || !currentlyFocusedCell) {
    return null;
  }

  const tableData = tableValues[currentlyFocusedCell];
  if (!tableData) {
    return null;
  }
  const { rows } = tableData;
  const currentRow = rows.at(selectedRowIdx);

  const rowValues: Record<string, Cell<unknown, unknown>> = {};
  const cells = currentRow?.getAllCells() ?? [];
  for (const cell of cells) {
    if (cell.column.id === SELECT_COLUMN_ID) {
      continue;
    }
    rowValues[cell.column.id] = cell;
  }

  // Selects the last row if selected row is out of bounds
  if (selectedRowIdx >= rows.length) {
    setSelectedRowIdx(rows.length - 1);
  }

  const searchedRows = Object.entries(rowValues).filter(
    ([columnName, cell]) => {
      const colName = columnName.toLowerCase();
      const cellValue = String(cell.getValue()).toLowerCase();
      const searchQueryLower = searchQuery.toLowerCase();
      return (
        colName.includes(searchQueryLower) ||
        cellValue.includes(searchQueryLower)
      );
    },
  );

  const renderModeToggle = () => {
    return (
      <div className="flex flex-row items-center gap-1">
        <Tooltip content={isPinned ? "Turn off overlay" : "Overlay content"}>
          <Button
            variant={isPinned ? "link" : "ghost"}
            size="icon"
            onClick={() => setIsPinned(!isPinned)}
          >
            <PinIcon className="w-4 h-4" />
          </Button>
        </Tooltip>
      </div>
    );
  };

  const handleSelectRow = (rowIdx: number) => {
    // wrap around if out of bounds
    if (rowIdx < 0) {
      rowIdx = rows.length - 1;
    } else if (rowIdx >= rows.length) {
      rowIdx = 0;
    }
    setSelectedRowIdx(rowIdx);
  };

  const children = (
    <div className="mt-2">
      <div className="flex flex-row justify-between items-center my-1 mx-2">
        {renderModeToggle()}
        <Button
          variant="linkDestructive"
          size="icon"
          onClick={() => setIsOpen(false)}
          aria-label="Close selection panel"
        >
          <XIcon className="w-4 h-4" />
        </Button>
      </div>

      {/* <h1 className="text-md font-bold tracking-wide text-center mb-3">
        Selection Panel
      </h1> */}

      <div className="flex flex-col gap-2 mt-4">
        <div className="flex flex-row gap-2 justify-end mr-2">
          <Button
            variant="outline"
            size="xs"
            className="px-1 h-5 w-5"
            onClick={() => handleSelectRow(selectedRowIdx - 1)}
          >
            <ChevronLeft />
          </Button>
          <span className="text-sm">
            {selectedRowIdx + 1} of {rows.length}
          </span>
          <Button
            variant="outline"
            size="xs"
            className="px-1 h-5 w-5"
            onClick={() => handleSelectRow(selectedRowIdx + 1)}
          >
            <ChevronRight />
          </Button>
        </div>

        <div className="mx-2 my-2">
          <Input
            placeholder="Search"
            onChange={(e) => setSearchQuery(e.target.value)}
            icon={<SearchIcon className="w-4 h-4" />}
          />
        </div>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-1/3">Column</TableHead>
              <TableHead className="w-2/3">Value</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {searchedRows.map(([columnName, cell]) => {
              const Icon =
                DATA_TYPE_ICON[
                  cell.column.columnDef.meta?.dataType || "unknown"
                ];
              return (
                <TableRow key={columnName}>
                  <TableCell className="flex flex-row items-center gap-1.5">
                    <Icon className="w-4 h-4 p-0.5 rounded-sm bg-muted" />
                    {columnName}
                  </TableCell>
                  <TableCell>{String(cell.getValue())}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );

  if (isPinned) {
    return <ResizableComponent>{children}</ResizableComponent>;
  }

  return (
    <>
      <PanelResizeHandle
        onDragging={handleDragging}
        className="resize-handle border-border z-20 no-print border-l"
      />
      <Panel>{children}</Panel>
    </>
  );
};

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
