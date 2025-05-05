/* Copyright 2024 Marimo. All rights reserved. */

import {
  ChevronLeft,
  ChevronRight,
  SearchIcon,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DATA_TYPE_ICON } from "@/components/datasets/icons";
import { Input } from "@/components/ui/input";
import { CopyClipboardIcon } from "@/components/icons/copy-icon";
import { useState } from "react";
import { useAsyncData } from "@/hooks/useAsyncData";
import type { FieldTypesWithExternalType } from "../types";
export interface DataSelectionPanelProps {
  rowIdx: number;
  totalRows: number;
  fieldTypes: FieldTypesWithExternalType | undefined | null;
  getRow: (rowIdx: number) => Promise<Record<string, unknown>>;
}

export const DataSelectionPanel: React.FC<DataSelectionPanelProps> = ({
  rowIdx,
  totalRows,
  fieldTypes,
  getRow,
}) => {
  return (
    <DataSelection
      rowIdx={rowIdx}
      totalRows={totalRows}
      fieldTypes={fieldTypes}
      getRow={getRow}
    />
  );
};

const DataSelection = ({
  rowIdx,
  totalRows,
  fieldTypes,
  getRow,
}: {
  rowIdx: number;
  totalRows: number;
  fieldTypes: FieldTypesWithExternalType | undefined | null;
  getRow: (rowIdx: number) => Promise<Record<string, unknown>>;
}) => {
  const [selectedRowIdx, setSelectedRowIdx] = useState(rowIdx);
  const [searchQuery, setSearchQuery] = useState("");

  const { data: currentRow } = useAsyncData(async () => {
    return getRow(selectedRowIdx);
  }, [getRow, selectedRowIdx]);

  const rowValues: Record<string, unknown> = currentRow ?? {};
  // const cells = currentRow?.getAllCells() ?? [];
  // for (const cell of cells) {
  //   if (
  //     cell.column.id === SELECT_COLUMN_ID ||
  //     cell.column.id === INDEX_COLUMN_NAME
  //   ) {
  //     continue;
  //   }
  //   if (cell.column.id.startsWith(NAMELESS_COLUMN_PREFIX)) {
  //     // Leave the column name empty
  //     cell.column.id = "";
  //   }
  //   rowValues[cell.column.id] = cell;
  // }

  // Selects the last row if selected row is out of bounds
  // if (selectedRowIdx >= totalRows) {
  //   setSelectedRowIdx(rows.length - 1);
  // }

  const handleSelectRow = (rowIdx: number) => {
    if (rowIdx < 0 || rowIdx >= totalRows) {
      return;
    }
    setSelectedRowIdx(rowIdx);
  };

  const getDataTypeIcon = (columnName: string) => {
    if (!fieldTypes) {
      return null;
    }

    const dataType = fieldTypes.find(
      (field) => field[0] === columnName,
    )?.[1][0];
    return DATA_TYPE_ICON[dataType || "unknown"];
  };

  const searchedRows = filterRows(rowValues, searchQuery);

  const buttonStyles = "h-6 w-6 p-0.5";

  return (
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
          Row {selectedRowIdx + 1} of {totalRows}
        </span>
        <Button
          variant="outline"
          size="xs"
          className={buttonStyles}
          onClick={() => handleSelectRow(selectedRowIdx + 1)}
          disabled={selectedRowIdx === totalRows - 1}
          aria-label="Next row"
        >
          <ChevronRight />
        </Button>
        <Button
          variant="outline"
          size="xs"
          className={buttonStyles}
          onClick={() => handleSelectRow(totalRows - 1)}
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
          {searchedRows.map(([columnName, columnValue]) => {
            const Icon = getDataTypeIcon(columnName);
            // TODO: Add cell content rendering
            // const cellContent = renderCellValue(
            //   cell.column,
            //   cell.renderValue,
            //   cell.getValue,
            //   Functions.NOOP,
            //   "text-left break-all",
            // );

            const cellValue = columnValue;
            const cellValueString =
              typeof cellValue === "object"
                ? JSON.stringify(cellValue)
                : String(cellValue);

            return (
              <TableRow key={columnName} className="group">
                <TableCell className="flex flex-row items-center gap-1.5">
                  {Icon && (
                    <Icon className="w-4 h-4 p-0.5 rounded-sm bg-muted" />
                  )}
                  {columnName}
                </TableCell>
                <TableCell>
                  <div className="flex flex-row items-center justify-between gap-1">
                    {cellValueString}
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
  );
};

export function filterRows(
  rowValues: Record<string, unknown>,
  searchQuery: string,
) {
  return Object.entries(rowValues).filter(([columnName, columnValue]) => {
    const colName = columnName.toLowerCase();

    let columnValueString =
      typeof columnValue === "object"
        ? JSON.stringify(columnValue)
        : String(columnValue);
    columnValueString = columnValueString.toLowerCase();
    const searchQueryLower = searchQuery.toLowerCase();

    return (
      colName.includes(searchQueryLower) ||
      columnValueString.includes(searchQueryLower)
    );
  });
}
