/* Copyright 2024 Marimo. All rights reserved. */

import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import type { PreviewColumn } from "@/plugins/impl/DataTablePlugin";
import {
  INDEX_COLUMN_NAME,
  SELECT_COLUMN_ID,
  type FieldTypesWithExternalType,
} from "../types";
import { NAMELESS_COLUMN_PREFIX } from "../columns";
import { DATA_TYPE_ICON } from "@/components/datasets/icons";
import { prettifyRowColumnCount } from "../pagination";
import type { DataType } from "@/core/kernel/messages";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { CopyClipboardIcon } from "@/components/icons/copy-icon";
import React from "react";
import { useAsyncData } from "@/hooks/useAsyncData";
import type { TopLevelFacetedUnitSpec } from "@/plugins/impl/data-explorer/queries/types";
import {
  AddDataframeChart,
  renderPreviewError,
  renderStats,
} from "@/components/datasources/column-preview";
import { ColumnPreviewContainer } from "@/components/datasources/components";

interface ColumnExplorerPanelProps {
  previewColumn: PreviewColumn;
  fieldTypes: FieldTypesWithExternalType | undefined | null;
  totalRows: number | "too_many";
  totalColumns: number;
}

export const ColumnExplorerPanel = ({
  previewColumn,
  fieldTypes,
  totalRows,
  totalColumns,
}: ColumnExplorerPanelProps) => {
  // TODO: Add copy all column names

  return (
    <div className="mt-3 mb-3">
      <span className="text-sm font-semibold ml-1">
        {prettifyRowColumnCount(totalRows, totalColumns)}
      </span>
      <Command className="h-5/6">
        <CommandInput placeholder="Search columns..." />
        <CommandList className="max-h-full">
          <CommandEmpty>No results.</CommandEmpty>
          {fieldTypes?.map(([columnName, [dataType, externalType]]) => {
            if (
              columnName === SELECT_COLUMN_ID ||
              columnName === INDEX_COLUMN_NAME ||
              columnName.startsWith(NAMELESS_COLUMN_PREFIX)
            ) {
              return null;
            }

            return (
              <ColumnItem
                key={columnName}
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

  const Icon = dataType ? DATA_TYPE_ICON[dataType] : null;

  return (
    <>
      <CommandItem key={columnName} onSelect={() => setIsExpanded(!isExpanded)}>
        <div className="flex flex-row items-center gap-1.5 group w-full">
          {Icon && <Icon className="w-4 h-4 p-0.5 rounded-sm bg-muted" />}
          <span className={isExpanded ? "font-semibold" : ""}>
            {columnName}
          </span>
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
            <span className="text-xs text-muted-foreground">
              {externalType}
            </span>
          </div>
        </div>
      </CommandItem>
      {isExpanded && (
        <ColumnPreview
          previewColumn={previewColumn}
          columnName={columnName}
          dataType={dataType}
        />
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
  const { data, error, loading } = useAsyncData(async () => {
    const response = await previewColumn({ column: columnName });
    return response;
  }, []);

  // TODO: Display errors and loading state nicely
  if (error) {
    return (
      <div className="text-xs text-muted-foreground p-2 border border-muted rounded flex items-center">
        <span>{error.message}</span>
      </div>
    );
  }

  if (loading) {
    return <span>Loading...</span>;
  }

  if (!data) {
    return <span>No data</span>;
  }

  const {
    chart_spec,
    chart_code,
    chart_max_rows_errors,
    error: previewError,
    missing_packages,
    stats,
  } = data;

  const errorState =
    previewError && renderPreviewError(previewError, missing_packages);

  const previewStats = stats && renderStats(stats, dataType);

  const updateSpec = (spec: TopLevelFacetedUnitSpec) => {
    return {
      ...spec,
      config: { ...spec.config, background: "transparent" },
    };
  };
  const chart = chart_spec && (
    <LazyVegaLite
      spec={updateSpec(JSON.parse(chart_spec) as TopLevelFacetedUnitSpec)}
      width={"container" as unknown as number}
      height={100}
      actions={false}
      // theme={theme === "dark" ? "dark" : "vox"}
    />
  );

  const addDataframeChart = chart_code && (
    <AddDataframeChart chartCode={chart_code} />
  );

  const chartMaxRowsWarning = chart_max_rows_errors && (
    <span className="text-xs text-muted-foreground">
      Too many rows to render the chart.
    </span>
  );

  return (
    <ColumnPreviewContainer>
      {errorState}
      {addDataframeChart}
      {chartMaxRowsWarning}
      {chart}
      {previewStats}
    </ColumnPreviewContainer>
  );
};

const LazyVegaLite = React.lazy(() =>
  import("react-vega").then((m) => ({ default: m.VegaLite })),
);
