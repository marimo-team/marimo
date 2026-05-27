/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

// tanstack/table is not compatible with React compiler
// https://github.com/TanStack/table/issues/5567

import {
  ChevronDownIcon,
  ChevronRightIcon,
  EyeIcon,
  EyeOffIcon,
} from "lucide-react";
import { useState } from "react";
import { useLocale } from "react-aria";
import {
  AddDataframeChart,
  renderChart,
  renderPreviewError,
  renderStats,
} from "@/components/datasources/column-preview";
import {
  ColumnName,
  ColumnPreviewContainer,
  EmptyState,
  ErrorState,
  LoadingState,
} from "@/components/datasources/components";
import { ErrorBoundary } from "@/components/editor/boundary/ErrorBoundary";
import { CopyClipboardIcon } from "@/components/icons/copy-icon";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Tooltip } from "@/components/ui/tooltip";
import type { DataType } from "@/core/kernel/messages";
import { useAsyncData } from "@/hooks/useAsyncData";
import type { PreviewColumn } from "@/plugins/impl/DataTablePlugin";
import { useTheme } from "@/theme/useTheme";
import { NAMELESS_COLUMN_PREFIX } from "../columns";
import { prettifyRowColumnCount } from "../pagination";
import {
  type FieldTypesWithExternalType,
  INDEX_COLUMN_NAME,
  SELECT_COLUMN_ID,
} from "../types";
import { smartMatch } from "@/utils/smartMatch";
import type { Column, Table } from "@tanstack/react-table";
import { cn } from "@/utils/cn";
import { getColumnCountForDisplay } from "../hooks/use-column-visibility";

interface ColumnExplorerPanelProps<TData> {
  previewColumn: PreviewColumn;
  fieldTypes: FieldTypesWithExternalType | undefined | null;
  totalRows: number | "too_many";
  totalColumns: number;
  tableId: string;
  table: Table<TData>;
}

export function ColumnExplorerPanel<TData>({
  previewColumn,
  fieldTypes,
  totalRows,
  totalColumns,
  tableId,
  table,
}: ColumnExplorerPanelProps<TData>) {
  const [searchValue, setSearchValue] = useState("");
  const { locale } = useLocale();
  const columns = fieldTypes?.filter(([columnName]) => {
    if (
      columnName === SELECT_COLUMN_ID ||
      columnName === INDEX_COLUMN_NAME ||
      columnName.startsWith(NAMELESS_COLUMN_PREFIX)
    ) {
      return false;
    }
    return true;
  });

  const filteredColumns = columns?.filter(([columnName]) => {
    return smartMatch(searchValue, columnName);
  });

  const {
    totalColumns: effectiveTotalColumns,
    hiddenColumns: hiddenColumnCount,
  } = getColumnCountForDisplay(table, totalColumns);

  const { rowsAndColumns, hiddenSuffix } = prettifyRowColumnCount({
    numRows: totalRows,
    totalColumns: effectiveTotalColumns,
    locale,
    hiddenColumns: hiddenColumnCount,
  });

  return (
    <div className="mb-3">
      <div className="text-xs font-semibold ml-2 flex items-center gap-1">
        {rowsAndColumns}
        {hiddenColumnCount > 0 && <span>{hiddenSuffix}</span>}
        <CopyClipboardIcon
          tooltip="Copy column names"
          value={columns?.map(([columnName]) => columnName).join(",\n") || ""}
          className="h-3 w-3"
        />
        {hiddenColumnCount > 0 && (
          <Button
            variant="link"
            size="xs"
            className="h-auto p-0"
            onClick={() => table.resetColumnVisibility(true)}
          >
            Unhide all
          </Button>
        )}
      </div>
      <Command className="h-5/6 bg-background" shouldFilter={false}>
        <CommandInput
          placeholder="Search columns..."
          value={searchValue}
          onValueChange={(value) => setSearchValue(value)}
        />
        <CommandList className="max-h-full">
          <CommandEmpty>No results.</CommandEmpty>
          {filteredColumns?.map(
            ([columnName, [dataType, externalType]], index) => {
              const column = table.getColumn(columnName);

              return (
                <ColumnItem
                  // Tables may have the same column names, hence we use tableId to make it unique
                  key={`${tableId}-${columnName}`}
                  columnName={columnName}
                  column={column}
                  dataType={dataType}
                  externalType={externalType}
                  previewColumn={previewColumn}
                  defaultExpanded={index === 0}
                />
              );
            },
          )}
        </CommandList>
      </Command>
    </div>
  );
}

function ColumnItem<TData>({
  columnName,
  column,
  dataType,
  externalType,
  previewColumn,
  defaultExpanded = false,
}: {
  columnName: string;
  column?: Column<TData, unknown>;
  dataType: DataType;
  externalType: string;
  previewColumn: PreviewColumn;
  defaultExpanded?: boolean;
}) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  const columnText = (
    <span className={isExpanded ? "font-semibold" : ""}>{columnName}</span>
  );

  return (
    <>
      <CommandItem
        key={columnName}
        onSelect={() => setIsExpanded(!isExpanded)}
        className="flex flex-row items-center gap-1.5 group w-full cursor-pointer"
      >
        {isExpanded ? (
          <ChevronDownIcon className="w-3 h-3 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRightIcon className="w-3 h-3 shrink-0 text-muted-foreground" />
        )}
        <ColumnName columnName={columnText} dataType={dataType} />
        <div className="ml-auto flex items-center gap-0.5">
          <CopyClipboardIcon
            tooltip="Copy column name"
            value={columnName}
            className="h-3 w-3"
            buttonClassName={cn(
              "inline-flex items-center justify-center rounded-md h-6 w-6",
              "group-hover:opacity-100 opacity-0 hover:bg-muted text-muted-foreground hover:text-primary",
            )}
          />
          {column?.getCanHide() && (
            <Tooltip
              content={column.getIsVisible() ? "Hide column" : "Show column"}
              delayDuration={400}
            >
              <Button
                variant="text"
                size="icon"
                className={cn(
                  "hover:bg-muted text-muted-foreground hover:text-primary",
                  column.getIsVisible()
                    ? "group-hover:opacity-100 opacity-0"
                    : "opacity-100",
                )}
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  column.toggleVisibility(!column.getIsVisible());
                }}
              >
                {column.getIsVisible() ? (
                  <EyeIcon className="h-3 w-3" strokeWidth={2.5} />
                ) : (
                  <EyeOffIcon className="h-3 w-3" strokeWidth={2.5} />
                )}
              </Button>
            </Tooltip>
          )}
          <span className="text-xs text-muted-foreground">{externalType}</span>
        </div>
      </CommandItem>
      {isExpanded && (
        <ErrorBoundary>
          <ColumnPreview
            previewColumn={previewColumn}
            columnName={columnName}
            dataType={dataType}
          />
        </ErrorBoundary>
      )}
    </>
  );
}

const ColumnPreview = ({
  previewColumn,
  columnName,
  dataType,
}: {
  previewColumn: PreviewColumn;
  columnName: string;
  dataType: DataType;
}) => {
  const { theme } = useTheme();
  const { locale } = useLocale();

  const {
    data,
    error,
    isPending,
    refetch: refetchPreview,
  } = useAsyncData(async () => {
    const response = await previewColumn({ column: columnName });
    return response;
  }, []);

  if (error) {
    return <ErrorState error={error} />;
  }

  if (isPending) {
    return <LoadingState message="Loading..." />;
  }

  if (!data) {
    return <EmptyState content="No data" className="pl-4" />;
  }

  const {
    chart_spec,
    chart_code,
    error: previewError,
    missing_packages,
    stats,
  } = data;

  const errorState =
    previewError &&
    renderPreviewError({
      error: previewError,
      missingPackages: missing_packages,
      refetchPreview,
    });

  const previewStats = stats && renderStats({ stats, dataType, locale });

  const chart = chart_spec && renderChart(chart_spec, theme);

  const addDataframeChart = chart_code && (
    <AddDataframeChart chartCode={chart_code} />
  );

  return (
    <ColumnPreviewContainer className="px-2 py-1">
      {errorState}
      {addDataframeChart}
      {chart}
      {previewStats}
    </ColumnPreviewContainer>
  );
};
