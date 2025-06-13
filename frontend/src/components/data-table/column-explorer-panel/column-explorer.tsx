/* Copyright 2024 Marimo. All rights reserved. */

import { useState } from "react";
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

interface ColumnExplorerPanelProps {
  previewColumn: PreviewColumn;
  fieldTypes: FieldTypesWithExternalType | undefined | null;
  totalRows: number | "too_many";
  totalColumns: number;
  tableId: string;
}

export const ColumnExplorerPanel = ({
  previewColumn,
  fieldTypes,
  totalRows,
  totalColumns,
  tableId,
}: ColumnExplorerPanelProps) => {
  const [searchValue, setSearchValue] = useState("");
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
    return columnName.toLowerCase().includes(searchValue.toLowerCase());
  });

  return (
    <div className="mt-5 mb-3">
      <span className="text-xs font-semibold ml-2 flex">
        {prettifyRowColumnCount(totalRows, totalColumns)}
        <CopyClipboardIcon
          tooltip="Copy column names"
          value={columns?.map(([columnName]) => columnName).join(",\n") || ""}
          className="h-3 w-3 ml-1 mt-0.5"
        />
      </span>
      <Command className="h-5/6" shouldFilter={false}>
        <CommandInput
          placeholder="Search columns..."
          value={searchValue}
          onValueChange={(value) => setSearchValue(value)}
        />
        <CommandList className="max-h-full">
          <CommandEmpty>No results.</CommandEmpty>
          {filteredColumns?.map(([columnName, [dataType, externalType]]) => {
            return (
              <ColumnItem
                // Tables may have the same column names, hence we use tableId to make it unique
                key={`${tableId}-${columnName}`}
                columnName={columnName}
                dataType={dataType}
                externalType={externalType}
                previewColumn={previewColumn}
              />
            );
          })}
        </CommandList>
      </Command>
    </div>
  );
};

const ColumnItem = ({
  columnName,
  dataType,
  externalType,
  previewColumn,
}: {
  columnName: string;
  dataType: DataType;
  externalType: string;
  previewColumn: PreviewColumn;
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

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
        <ColumnName columnName={columnText} dataType={dataType} />
        <div className="ml-auto">
          <Tooltip content="Copy column name" delayDuration={400}>
            <Button
              variant="text"
              size="icon"
              className="group-hover:opacity-100 opacity-0 hover:bg-muted text-muted-foreground hover:text-foreground"
            >
              <CopyClipboardIcon
                tooltip={false}
                value={columnName}
                className="h-3 w-3"
              />
            </Button>
          </Tooltip>
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
};

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

  const { data, error, isPending } = useAsyncData(async () => {
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
    previewError && renderPreviewError(previewError, missing_packages);

  const previewStats = stats && renderStats(stats, dataType);

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
