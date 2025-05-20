/* Copyright 2024 Marimo. All rights reserved. */

import {
  ChevronLeft,
  ChevronRight,
  SearchIcon,
  ChevronsLeft,
  ChevronsRight,
  AlertTriangle,
  Info,
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
import { useState, useRef } from "react";
import { useAsyncData } from "@/hooks/useAsyncData";
import {
  INDEX_COLUMN_NAME,
  SELECT_COLUMN_ID,
  TOO_MANY_ROWS,
  type TooManyRows,
  type FieldTypesWithExternalType,
} from "../types";
import { prettifyRowCount } from "../pagination";
import type { GetRowResult } from "@/plugins/impl/DataTablePlugin";
import { NAMELESS_COLUMN_PREFIX } from "../columns";
import { Banner, ErrorBanner } from "@/plugins/impl/common/error-banner";
import type { Column } from "@tanstack/react-table";
import { renderCellValue } from "../columns";
import { useKeydownOnElement } from "@/hooks/useHotkey";

export interface RowViewerPanelProps {
  rowIdx: number;
  setRowIdx: (rowIdx: number) => void;
  totalRows: number | TooManyRows;
  fieldTypes: FieldTypesWithExternalType | undefined | null;
  getRow: (rowIdx: number) => Promise<GetRowResult>;
}

export const RowViewerPanel: React.FC<RowViewerPanelProps> = ({
  rowIdx,
  setRowIdx,
  totalRows,
  fieldTypes,
  getRow,
}: RowViewerPanelProps) => {
  const [searchQuery, setSearchQuery] = useState("");
  const panelRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const tooManyRows = totalRows === TOO_MANY_ROWS;

  const { data: rows, error } = useAsyncData(async () => {
    const data = await getRow(rowIdx);
    return data.rows;
  }, [getRow, rowIdx, totalRows]);

  const handleSelectRow = (rowIdx: number) => {
    if (rowIdx < 0 || (typeof totalRows === "number" && rowIdx >= totalRows)) {
      return;
    }
    setRowIdx(rowIdx);
  };

  // Total rows may change after the row viewer panel is opened
  if (!tooManyRows && rowIdx > totalRows) {
    handleSelectRow(totalRows - 1);
  }

  useKeydownOnElement(panelRef, {
    ArrowLeft: (e) => {
      if (e?.target === searchInputRef.current) {
        return false;
      }
      handleSelectRow(rowIdx - 1);
    },
    ArrowRight: (e) => {
      if (e?.target === searchInputRef.current) {
        return false;
      }
      handleSelectRow(rowIdx + 1);
    },
  });

  const buttonStyles = "h-6 w-6 p-0.5";

  const renderTable = () => {
    if (error) {
      return <ErrorBanner error={error} className="p-4 mx-3 mt-5" />;
    }

    if (totalRows === 0) {
      return (
        <SimpleBanner kind="info" Icon={Info} message="No rows selected" />
      );
    }

    if (!rows) {
      return (
        <SimpleBanner
          kind="warn"
          Icon={AlertTriangle}
          message="No data available. Please report the issue."
        />
      );
    }

    if (rows.length !== 1) {
      return (
        <SimpleBanner
          kind="warn"
          Icon={AlertTriangle}
          message={`Expected 1 row, got ${rows.length} rows. Please report the issue.`}
        />
      );
    }

    const currentRow = rows[0];
    if (typeof currentRow !== "object" || currentRow === null) {
      return (
        <SimpleBanner
          kind="warn"
          Icon={AlertTriangle}
          message="Row is not an object. Please report the issue."
        />
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

    return (
      <Table className="mb-4">
        <TableHeader>
          <TableRow>
            <TableHead className="w-1/4">Column</TableHead>
            <TableHead className="w-3/4">Value</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {fieldTypes?.map(([columnName, [dataType, externalType]]) => {
            const Icon = dataType ? DATA_TYPE_ICON[dataType] : null;
            const columnValue = rowValues[columnName];

            if (!inSearchQuery(columnName, columnValue, searchQuery)) {
              return null;
            }

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
              () => columnValue,
              () => columnValue,
              undefined,
              "text-left break-all",
            );

            const copyValue =
              typeof columnValue === "object"
                ? JSON.stringify(columnValue)
                : String(columnValue);

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
    <div
      className="flex flex-col gap-3 mt-4 focus:outline-none"
      ref={panelRef}
      tabIndex={-1}
    >
      <div className="flex flex-row gap-2 justify-end items-center mr-2">
        <Button
          variant="outline"
          size="xs"
          className={buttonStyles}
          onClick={() => handleSelectRow(0)}
          disabled={rowIdx === 0}
          aria-label="Go to first row"
        >
          <ChevronsLeft />
        </Button>
        <Button
          variant="outline"
          size="xs"
          className={buttonStyles}
          onClick={() => handleSelectRow(rowIdx - 1)}
          disabled={rowIdx === 0}
          aria-label="Previous row"
        >
          <ChevronLeft />
        </Button>
        <span className="text-xs">
          {tooManyRows
            ? `Row ${rowIdx + 1}`
            : `Row ${rowIdx + 1} of ${prettifyRowCount(totalRows)}`}
        </span>
        <Button
          variant="outline"
          size="xs"
          className={buttonStyles}
          onClick={() => handleSelectRow(rowIdx + 1)}
          disabled={!tooManyRows && rowIdx === totalRows - 1}
          aria-label="Next row"
        >
          <ChevronRight />
        </Button>
        <Button
          variant="outline"
          size="xs"
          className={buttonStyles}
          onClick={() => {
            if (!tooManyRows) {
              handleSelectRow(totalRows - 1);
            }
          }}
          disabled={tooManyRows || rowIdx === totalRows - 1}
          aria-label="Go to last row"
        >
          <ChevronsRight />
        </Button>
      </div>

      <div className="mx-2 -mb-1">
        <Input
          ref={searchInputRef}
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

export function inSearchQuery(
  columnName: string,
  columnValue: unknown,
  searchQuery: string,
) {
  const colName = columnName.toLowerCase();
  const searchQueryLower = searchQuery.toLowerCase();

  let columnValueString =
    typeof columnValue === "object"
      ? JSON.stringify(columnValue)
      : String(columnValue);
  columnValueString = columnValueString.toLowerCase();

  return (
    colName.includes(searchQueryLower) ||
    columnValueString.includes(searchQueryLower)
  );
}

const SimpleBanner: React.FC<{
  kind: "info" | "warn" | "danger";
  Icon: React.FC<React.SVGProps<SVGSVGElement>>;
  message: string;
}> = ({ kind, Icon, message }) => {
  return (
    <Banner
      kind={kind}
      className="p-4 mx-3 mt-3 flex flex-row items-center gap-2"
    >
      <Icon className="w-5 h-5" />
      <span>{message}</span>
    </Banner>
  );
};
