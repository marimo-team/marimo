/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { PlusSquareIcon } from "lucide-react";
import React, { Suspense } from "react";
import { maybeAddAltairImport } from "@/core/cells/add-missing-import";
import { useCellActions } from "@/core/cells/cells";
import { useLastFocusedCellId } from "@/core/cells/focus";
import { autoInstantiateAtom } from "@/core/config/config";
import type { SQLTableContext } from "@/core/datasets/data-source-connections";
import type {
  DataColumnPreview,
  DataTable,
  DataTableColumn,
  DataType,
} from "@/core/kernel/messages";
import { previewDatasetColumn } from "@/core/network/requests";
import { useOnMount } from "@/hooks/useLifecycle";
import type { TopLevelFacetedUnitSpec } from "@/plugins/impl/data-explorer/queries/types";
import { type Theme, useTheme } from "@/theme/useTheme";
import { Events } from "@/utils/events";
import { prettyNumber } from "@/utils/numbers";
import { CopyClipboardIcon } from "../icons/copy-icon";
import { Spinner } from "../icons/spinner";
import { Button } from "../ui/button";
import { Tooltip } from "../ui/tooltip";
import { ColumnPreviewContainer } from "./components";
import { InstallPackageButton } from "./install-package-button";
import { convertStatsName, sqlCode } from "./utils";

const LazyVegaLite = React.lazy(() =>
  import("react-vega").then((m) => ({ default: m.VegaLite })),
);

export const DatasetColumnPreview: React.FC<{
  table: DataTable;
  column: DataTableColumn;
  onAddColumnChart: (code: string) => void;
  preview: DataColumnPreview | undefined;
  sqlTableContext?: SQLTableContext;
}> = ({ table, column, preview, onAddColumnChart, sqlTableContext }) => {
  const { theme } = useTheme();

  useOnMount(() => {
    if (preview) {
      return;
    }

    // Do not fetch previews for custom SQL connections or catalogs
    if (table.source_type === "connection" || table.source_type === "catalog") {
      return;
    }

    previewDatasetColumn({
      source: table.source,
      tableName: table.name,
      columnName: column.name,
      sourceType: table.source_type,
      fullyQualifiedTableName: sqlTableContext
        ? `${sqlTableContext.database}.${sqlTableContext.schema}.${table.name}`
        : table.name,
    });
  });

  if (table.source_type === "connection") {
    return (
      <span className="text-xs text-muted-foreground gap-2 flex items-center justify-between pl-7">
        {column.name} ({column.external_type})
        <Button
          variant="outline"
          size="xs"
          onClick={Events.stopPropagation(() => {
            onAddColumnChart(sqlCode(table, column.name, sqlTableContext));
          })}
        >
          <PlusSquareIcon className="h-3 w-3 mr-1" /> Add SQL cell
        </Button>
      </span>
    );
  }

  if (table.source_type === "catalog") {
    return (
      <span className="text-xs text-muted-foreground gap-2 flex items-center justify-between pl-7">
        {column.name} ({column.external_type})
      </span>
    );
  }

  if (!preview) {
    return <span className="text-xs text-muted-foreground">Loading...</span>;
  }

  const error =
    preview.error &&
    renderPreviewError(preview.error, preview.missing_packages);

  const stats = preview.stats && renderStats(preview.stats, column.type);

  const chart = preview.chart_spec && renderChart(preview.chart_spec, theme);

  const addDataframeChart = preview.chart_code &&
    table.source_type === "local" && (
      <AddDataframeChart chartCode={preview.chart_code} />
    );

  const addSQLChart = table.source_type === "duckdb" && (
    <Tooltip content="Add SQL cell" delayDuration={400}>
      <Button
        variant="outline"
        size="icon"
        className="z-10 bg-background absolute right-1 -top-1"
        onClick={Events.stopPropagation(() => {
          onAddColumnChart(sqlCode(table, column.name, sqlTableContext));
        })}
      >
        <PlusSquareIcon className="h-3 w-3" />
      </Button>
    </Tooltip>
  );

  if (!error && !stats && !chart) {
    return <span className="text-xs text-muted-foreground">No data</span>;
  }

  return (
    <ColumnPreviewContainer>
      {error}
      {addDataframeChart}
      {addSQLChart}
      {chart}
      {stats}
    </ColumnPreviewContainer>
  );
};

export function renderPreviewError(
  error: string,
  missing_packages?: string[] | null,
) {
  return (
    <div className="text-xs text-muted-foreground p-2 border border-border rounded flex items-center justify-between">
      <span>{error}</span>
      {missing_packages && (
        <InstallPackageButton
          packages={missing_packages}
          showMaxPackages={1}
          className="w-32"
        />
      )}
    </div>
  );
}

export function renderStats(
  stats: Record<string, string | number | boolean | null>,
  dataType: DataType,
) {
  return (
    <div className="gap-x-16 gap-y-1 grid grid-cols-2-fit border rounded p-2 empty:hidden">
      {Object.entries(stats).map(([key, value]) => {
        if (value == null) {
          return null;
        }

        return (
          <div key={key} className="flex items-center gap-1 group">
            <span className="text-xs min-w-[60px] capitalize">
              {convertStatsName(key, dataType)}
            </span>
            <span className="text-xs font-bold text-muted-foreground tracking-wide">
              {prettyNumber(value)}
            </span>
            <CopyClipboardIcon
              className="h-3 w-3 invisible group-hover:visible"
              value={String(value)}
            />
          </div>
        );
      })}
    </div>
  );
}

const LoadingChart = (
  <div className="flex justify-center">
    <Spinner className="size-4" />
  </div>
);

export function renderChart(chartSpec: string, theme: Theme) {
  const updateSpec = (spec: TopLevelFacetedUnitSpec) => {
    return {
      ...spec,
      background: "transparent",
      config: { ...spec.config, background: "transparent" },
    };
  };

  return (
    <Suspense fallback={LoadingChart}>
      <LazyVegaLite
        spec={updateSpec(JSON.parse(chartSpec) as TopLevelFacetedUnitSpec)}
        width={"container" as unknown as number}
        height={100}
        actions={false}
        theme={theme === "dark" ? "dark" : "vox"}
      />
    </Suspense>
  );
}

export const AddDataframeChart: React.FC<{
  chartCode: string;
}> = ({ chartCode }) => {
  const autoInstantiate = useAtomValue(autoInstantiateAtom);
  const lastFocusedCellId = useLastFocusedCellId();
  const { createNewCell } = useCellActions();

  const handleAddColumn = (chartCode: string) => {
    if (chartCode.includes("alt")) {
      maybeAddAltairImport(autoInstantiate, createNewCell, lastFocusedCellId);
    }
    createNewCell({
      code: chartCode,
      before: false,
      cellId: lastFocusedCellId ?? "__end__",
    });
  };

  return (
    <Tooltip content="Add chart to notebook" delayDuration={400}>
      <Button
        variant="outline"
        size="icon"
        className="z-10 bg-background absolute right-1 -top-0.5"
        onClick={Events.stopPropagation(() => handleAddColumn(chartCode))}
      >
        <PlusSquareIcon className="h-3 w-3" />
      </Button>
    </Tooltip>
  );
};
