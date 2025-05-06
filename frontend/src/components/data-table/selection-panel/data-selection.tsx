/* Copyright 2024 Marimo. All rights reserved. */

import {
  ChevronLeft,
  ChevronRight,
  SearchIcon,
  ChevronsLeft,
  ChevronsRight,
  AlertTriangle,
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
import {
  INDEX_COLUMN_NAME,
  SELECT_COLUMN_ID,
  type FieldTypesWithExternalType,
} from "../types";
import { prettifyRowCount } from "../pagination";
import type { GetRowResult } from "@/plugins/impl/DataTablePlugin";
import { NAMELESS_COLUMN_PREFIX } from "../columns";
import { Banner, ErrorBanner } from "@/plugins/impl/common/error-banner";
import type { Column } from "@tanstack/react-table";
import { renderCellValue } from "../columns";

export interface DataSelectionPanelProps {
  rowIdx: number;
  totalRows: number;
  fieldTypes: FieldTypesWithExternalType | undefined | null;
  getRow: (rowIdx: number) => Promise<GetRowResult>;
}

export const DataSelectionPanel: React.FC<DataSelectionPanelProps> = ({
  rowIdx,
  totalRows,
  fieldTypes,
  getRow,
}: DataSelectionPanelProps) => {
  const [selectedRowIdx, setSelectedRowIdx] = useState(rowIdx);
  const [searchQuery, setSearchQuery] = useState("");

  const { data: rows, error } = useAsyncData(async () => {
    const data = await getRow(selectedRowIdx);
    return data.rows;
  }, [getRow, selectedRowIdx]);

  if (error) {
    return <ErrorBanner error={error} className="p-4 mx-3 mt-5" />;
  }

  const handleSelectRow = (rowIdx: number) => {
    if (rowIdx < 0 || rowIdx >= totalRows) {
      return;
    }
    setSelectedRowIdx(rowIdx);
  };

  const buttonStyles = "h-6 w-6 p-0.5";

  const renderTable = () => {
    if (!rows) {
      return (
        <WarnBanner message="No data available. Please report the issue." />
      );
    }

    if (rows.length !== 1) {
      return (
        <WarnBanner
          message={`Expected 1 row, got ${rows.length} rows. Please report the issue.`}
        />
      );
    }

    const currentRow = rows[0];
    if (typeof currentRow !== "object" || currentRow === null) {
      return (
        <WarnBanner message="Row is not an object. Please report the issue." />
      );
    }

    const rowValues: Record<string, unknown> = {};
    for (const [columnName, columnValue] of Object.entries(currentRow)) {
      if (columnName === SELECT_COLUMN_ID || columnName === INDEX_COLUMN_NAME) {
        continue;
      }
      if (columnName.startsWith(NAMELESS_COLUMN_PREFIX)) {
        // Remove the prefix
        rowValues[columnName.slice(NAMELESS_COLUMN_PREFIX.length)] =
          columnValue;
      } else {
        rowValues[columnName] = columnValue;
      }
    }

    const searchedRows = filterRows(rowValues, searchQuery);

    return (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-1/4">Column</TableHead>
            <TableHead className="w-3/4">Value</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {searchedRows.map(([columnName, columnValue]) => {
            const dataType = fieldTypes?.find(
              ([name]) => name === columnName,
            )?.[1][0];
            const Icon = dataType ? DATA_TYPE_ICON[dataType] : null;
            const cellValue = columnValue;
            const mockColumn = {
              id: columnName,
              columnDef: {
                meta: {
                  dataType,
                },
              },
              getColumnFormatting: () => undefined,
              applyColumnFormatting: (value) => value,
            } as Column<unknown>;

            const cellContent = renderCellValue(
              mockColumn,
              () => cellValue,
              () => cellValue,
              undefined,
              "text-left break-all",
            );
            const copyValue =
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
                    {cellContent}
                    <CopyClipboardIcon
                      value={copyValue}
                      className="w-3 h-3 mr-1 text-muted-foreground cursor-pointer opacity-0 group-hover:opacity-100"
                    />
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    );
  };

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
          Row {selectedRowIdx + 1} of {prettifyRowCount(totalRows)}
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
      {renderTable()}
    </div>
  );
};

export function filterRows(rowValues: object, searchQuery: string) {
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

const WarnBanner: React.FC<{ message: string }> = ({ message }) => {
  return (
    <Banner
      kind="warn"
      className="p-4 mx-3 mt-3 flex flex-row items-center gap-2"
    >
      <AlertTriangle className="w-5 h-5" />
      <span>{message}</span>
    </Banner>
  );
};
