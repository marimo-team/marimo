/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import {
  ChevronRightIcon,
  DatabaseIcon,
  PlusIcon,
  PaintRollerIcon,
  PlusSquareIcon,
  XIcon,
  LoaderCircle,
  Table2Icon,
  EyeIcon,
} from "lucide-react";
import { Command, CommandInput, CommandItem } from "@/components/ui/command";
import { CommandList } from "cmdk";

import { cn } from "@/utils/cn";
import {
  closeAllColumnsAtom,
  datasetTablesAtom,
  expandedColumnsAtom,
  useDatasets,
} from "@/core/datasets/state";
import { DATA_TYPE_ICON } from "@/components/datasets/icons";
import { Button } from "@/components/ui/button";
import { cellIdsAtom, useCellActions } from "@/core/cells/cells";
import { useLastFocusedCellId } from "@/core/cells/focus";
import { atom, useAtom, useAtomValue, useSetAtom } from "jotai";
import { Tooltip } from "@/components/ui/tooltip";
import { PanelEmptyState } from "./empty-state";
import { previewDatasetColumn } from "@/core/network/requests";
import { prettyNumber } from "@/utils/numbers";
import { Events } from "@/utils/events";
import { CopyClipboardIcon } from "@/components/icons/copy-icon";
import { ErrorBoundary } from "../../boundary/ErrorBoundary";
import type { TopLevelFacetedUnitSpec } from "@/plugins/impl/data-explorer/queries/types";
import { useTheme } from "@/theme/useTheme";
import {
  maybeAddAltairImport,
  maybeAddMarimoImport,
} from "@/core/cells/add-missing-import";
import { autoInstantiateAtom } from "@/core/config/config";
import type {
  Database,
  DatabaseSchema,
  DataColumnPreview,
  DataTable,
  DataTableColumn,
} from "@/core/kernel/messages";
import { variablesAtom } from "@/core/variables/state";
import { sortBy } from "lodash-es";
import { logNever } from "@/utils/assertNever";
import { DatabaseLogo } from "@/components/databases/icon";
import { EngineVariable } from "@/components/databases/engine-variable";
import type { VariableName } from "@/core/variables/types";
import { dbDisplayName } from "@/components/databases/display";
import { AddDatabaseDialog } from "../../database/add-database-form";
import { enginesAtom, tablePreviewsAtom } from "@/core/datasets/databases";
import { PythonIcon } from "../../cell/code/icons";
import { PreviewSQLTable } from "@/core/functions/FunctionRegistry";
import { useAsyncData } from "@/hooks/useAsyncData";

const sortedTablesAtom = atom((get) => {
  const tables = get(datasetTablesAtom);
  const variables = get(variablesAtom);
  const cellIds = get(cellIdsAtom);

  // Sort tables by the index of the variable they are defined in
  return sortBy(tables, (table) => {
    // Put at the top
    if (!table.variable_name) {
      return -1;
    }
    const variable = Object.values(variables).find(
      (v) => v.name === table.variable_name,
    );
    if (!variable) {
      return 0;
    }

    const index = cellIds.inOrderIds.indexOf(variable.declaredBy[0]);
    if (index === -1) {
      return 0;
    }
    return index;
  });
});

export const DataSourcesPanel: React.FC = () => {
  const [searchValue, setSearchValue] = React.useState<string>("");

  const autoInstantiate = useAtomValue(autoInstantiateAtom);
  const lastFocusedCellId = useLastFocusedCellId();
  const closeAllColumns = useSetAtom(closeAllColumnsAtom);
  const { createNewCell } = useCellActions();
  const tables = useAtomValue(sortedTablesAtom);
  const engines = useAtomValue(enginesAtom);

  if (tables.length === 0 && engines.enginesMap.size === 0) {
    return (
      <PanelEmptyState
        title="No tables found"
        description="Any datasets/dataframes in the global scope will be shown here."
        action={
          <AddDatabaseDialog>
            <Button variant="outline" size="sm">
              Add database
              <PlusIcon className="h-4 w-4 ml-2" />
            </Button>
          </AddDatabaseDialog>
        }
        icon={<DatabaseIcon />}
      />
    );
  }

  const handleAddTable = (table: DataTable) => {
    maybeAddMarimoImport(autoInstantiate, createNewCell, lastFocusedCellId);
    let code = "";
    switch (table.source_type) {
      case "local":
        code = `mo.ui.table(${table.name})`;
        break;
      case "duckdb":
        code = `_df = mo.sql(f"SELECT * FROM ${table.name} LIMIT 100")`;
        break;
      case "connection":
        code = `_df = mo.sql(f"SELECT * FROM ${table.name} LIMIT 100", engine=${table.engine})`;
        break;
      default:
        logNever(table.source_type);
        break;
    }
    createNewCell({
      code: code,
      before: false,
      cellId: lastFocusedCellId ?? "__end__",
    });
  };

  const hasSearch = !!searchValue.trim();

  return (
    <Command className="border-b bg-background rounded-none h-full overflow-auto">
      <div className="flex items-center w-full">
        <CommandInput
          placeholder="Search tables..."
          className="h-6 m-1"
          value={searchValue}
          onValueChange={(value) => {
            // If searching, remove open previews
            if (value.length > 0) {
              closeAllColumns(true);
            }
            setSearchValue(value);
          }}
          rootClassName="flex-1 border-r"
        />
        {hasSearch && (
          <button
            type="button"
            className="float-right border-b px-2 m-0 h-full hover:bg-accent hover:text-accent-foreground"
            onClick={() => setSearchValue("")}
          >
            <XIcon className="h-4 w-4" />
          </button>
        )}

        <AddDatabaseDialog>
          <button
            type="button"
            className="float-right border-b px-2 m-0 h-full hover:bg-accent hover:text-accent-foreground"
          >
            <PlusIcon className="h-4 w-4" />
          </button>
        </AddDatabaseDialog>
      </div>

      {[...engines.enginesMap].map(([engineName, databaseMap]) => {
        const dialect = databaseMap.values().next().value?.dialect || "duckdb";
        return (
          <Engine
            key={engineName}
            name={engineName}
            dialect={dialect}
            hasChildren={databaseMap.size > 0}
          >
            {[...databaseMap.values()].map((database) => (
              <DatabaseItem key={database.name} database={database}>
                {database.schemas.map((schema) => (
                  <SchemaItem key={schema.name} schema={schema}>
                    <TableList
                      tables={Object.values(schema.tables)}
                      onAddTable={handleAddTable}
                      isSearching={hasSearch}
                      sqlTableContext={{
                        engine: engineName,
                        database: database.name,
                        schema: schema.name,
                      }}
                    />
                  </SchemaItem>
                ))}
              </DatabaseItem>
            ))}
          </Engine>
        );
      })}

      <DatasourceLabel>
        <PythonIcon className="h-4 w-4 text-muted-foreground" />
        <span>Python</span>
      </DatasourceLabel>
      <TableList
        onAddTable={handleAddTable}
        tables={tables}
        isSearching={hasSearch}
      />
    </Command>
  );
};

const Engine: React.FC<{
  name: string;
  dialect: string;
  children: React.ReactNode;
  hasChildren?: boolean;
}> = ({ name, dialect, children, hasChildren }) => {
  return (
    <>
      <DatasourceLabel>
        <DatabaseLogo
          className="h-4 w-4 text-muted-foreground"
          name={dialect}
        />
        <span>{dbDisplayName(dialect)}</span>
        <span className="text-xs text-muted-foreground">
          (<EngineVariable variableName={name as VariableName} />)
        </span>
      </DatasourceLabel>
      {hasChildren ? (
        children
      ) : (
        <EmptyState content="No databases available" className="pl-2" />
      )}
    </>
  );
};

const DatabaseItem: React.FC<{
  database: Database;
  children: React.ReactNode;
}> = ({ database, children }) => {
  const [isExpanded, setIsExpanded] = React.useState(false);

  const renderChildren = () => {
    if (!isExpanded) {
      return;
    }

    if (database.schemas.length === 0) {
      return <EmptyState content="No schemas available" className="pl-6" />;
    }

    return children;
  };

  return (
    <>
      <CommandItem
        className="text-sm flex flex-row gap-1 items-center border-b cursor-pointer"
        onSelect={() => setIsExpanded(!isExpanded)}
      >
        <RotatingChevron isExpanded={isExpanded} />
        <DatabaseIcon className="h-4 w-4 text-muted-foreground" />
        {database.name}
      </CommandItem>
      {renderChildren()}
    </>
  );
};

const SchemaItem: React.FC<{
  schema: DatabaseSchema;
  children: React.ReactNode;
}> = ({ schema, children }) => {
  const [isExpanded, setIsExpanded] = React.useState(false);

  return (
    <>
      <CommandItem
        className="py-1 text-sm flex flex-row gap-1 items-center border-b pl-5 cursor-pointer"
        onSelect={() => setIsExpanded(!isExpanded)}
      >
        <RotatingChevron isExpanded={isExpanded} />
        <PaintRollerIcon className="h-4 w-4 text-muted-foreground" />
        {schema.name}
      </CommandItem>
      {isExpanded && <div className="pl-5">{children}</div>}
    </>
  );
};

interface SQLTableContext {
  engine: string;
  database: string;
  schema: string;
}

const TableList: React.FC<{
  onAddTable: (table: DataTable) => void;
  isSearching: boolean;
  tables: DataTable[];
  sqlTableContext?: SQLTableContext;
}> = ({ tables, isSearching, onAddTable, sqlTableContext }) => {
  return (
    <CommandList className="flex flex-col overflow-auto">
      {tables.length === 0 ? (
        <EmptyState content="No tables found" className="pl-5" />
      ) : (
        tables.map((table) => (
          <DatasetTableItem
            key={table.name}
            table={table}
            forceMount={isSearching}
            onAddTable={() => onAddTable(table)}
            sqlTableContext={sqlTableContext}
          />
        ))
      )}
    </CommandList>
  );
};

const DatasetTableItem: React.FC<{
  table: DataTable;
  forceMount?: boolean;
  onAddTable: (table: DataTable) => void;
  sqlTableContext?: SQLTableContext;
}> = ({ table, onAddTable, sqlTableContext }) => {
  const [isExpanded, setIsExpanded] = React.useState(false);

  const [tablePreviews, setTablePreviews] = useAtom(tablePreviewsAtom);
  const tablePreview = tablePreviews.get(table.name);
  const tableDetailsExist = table.columns.length > 0;

  const { loading, error } = useAsyncData(async () => {
    // Only fetch table preview when the data is not passed in and doesn't exist in the atom
    if (isExpanded && !tableDetailsExist && sqlTableContext && !tablePreview) {
      const previewTable = await PreviewSQLTable.request({
        engine: sqlTableContext.engine,
        database: sqlTableContext.database,
        schema: sqlTableContext.schema,
        tableName: table.name,
      });

      if (!previewTable?.table) {
        throw new Error("No table found");
      }

      setTablePreviews((prev) => new Map(prev).set(table.name, previewTable));
    }
  }, [isExpanded, tableDetailsExist]);

  const renderRowsByColumns = () => {
    const label: string[] = [];
    if (table.num_rows != null) {
      label.push(`${table.num_rows} rows`);
    }
    if (table.num_columns != null) {
      label.push(`${table.num_columns} columns`);
    }

    if (label.length === 0) {
      return null;
    }

    return (
      <div className="flex flex-row gap-2 items-center pl-6 group-hover:hidden">
        <span className="text-xs text-muted-foreground">
          {label.join(", ")}
        </span>
      </div>
    );
  };

  const renderColumns = () => {
    if (loading) {
      return (
        <div className="pl-5 text-sm bg-blue-50 text-blue-500 flex items-center gap-2 p-2 h-7">
          <LoaderCircle className="h-4 w-4 animate-spin" />
          Loading columns...
        </div>
      );
    }

    if (error) {
      return (
        <div className="pl-5 text-sm bg-red-50 text-red-600 flex items-center gap-2 p-2 h-7">
          <XIcon className="h-4 w-4" />
          {error.message}
        </div>
      );
    }

    const columns = tableDetailsExist
      ? table.columns
      : tablePreview?.table?.columns || [];
    return columns.map((column) => (
      <DatasetColumnItem
        key={column.name}
        table={tablePreview?.table ?? table}
        column={column}
      />
    ));
  };

  const renderTableType = () => {
    if (table.source_type === "local") {
      return;
    }

    if (table.type === "table") {
      return (
        <Tooltip content="Table" delayDuration={100}>
          <Table2Icon className="h-3 w-3" />
        </Tooltip>
      );
    }

    if (table.type === "view") {
      return (
        <Tooltip content="View" delayDuration={100}>
          <EyeIcon className="h-3 w-3" />
        </Tooltip>
      );
    }
  };

  return (
    <>
      <CommandItem
        className={cn(
          "rounded-none py-1 group h-7 border-t cursor-pointer",
          table.source_type !== "local" && "pl-5",
        )}
        value={table.name}
        aria-selected={isExpanded}
        forceMount={true}
        onSelect={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex gap-2 items-center flex-1">
          {renderTableType()}
          <span className="text-sm">{table.name}</span>
        </div>
        {renderRowsByColumns()}
        <Tooltip content="Add table to notebook" delayDuration={400}>
          <Button
            className="group-hover:inline-flex hidden"
            variant="text"
            size="icon"
            onClick={Events.stopPropagation(() => onAddTable(table))}
          >
            <PlusSquareIcon className="h-3 w-3" />
          </Button>
        </Tooltip>
      </CommandItem>
      {isExpanded && renderColumns()}
    </>
  );
};

const DatasetColumnItem: React.FC<{
  table: DataTable;
  column: DataTableColumn;
}> = ({ table, column }) => {
  const [isExpanded, setIsExpanded] = React.useState(false);

  const setExpandedColumns = useSetAtom(expandedColumnsAtom);
  const closeAllColumns = useAtomValue(closeAllColumnsAtom);

  React.useEffect(() => {
    if (closeAllColumns) {
      setIsExpanded(false);
    }
  }, [closeAllColumns]);

  if (isExpanded) {
    setExpandedColumns(
      (prev) => new Set([...prev, `${table.name}:${column.name}`]),
    );
  } else {
    setExpandedColumns((prev) => {
      prev.delete(`${table.name}:${column.name}`);
      return new Set(prev);
    });
  }

  const Icon = DATA_TYPE_ICON[column.type];

  const autoInstantiate = useAtomValue(autoInstantiateAtom);
  const lastFocusedCellId = useLastFocusedCellId();
  const { createNewCell } = useCellActions();

  const { columnsPreviews } = useDatasets();

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
    <>
      <CommandItem
        className="rounded-none py-1 group cursor-pointer"
        key={`${table.name}.${column.name}`}
        value={`${table.name}.${column.name}`}
        onSelect={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex flex-row gap-2 items-center pl-6 flex-1">
          <Icon className="flex-shrink-0 h-3 w-3" strokeWidth={1.5} />
          <span>{column.name}</span>
        </div>
        <Tooltip content="Copy column name" delayDuration={400}>
          <Button
            variant="text"
            size="icon"
            className="group-hover:opacity-100 opacity-0 hover:bg-muted text-muted-foreground hover:text-foreground"
          >
            <CopyClipboardIcon
              tooltip={false}
              value={column.name}
              className="h-3 w-3"
            />
          </Button>
        </Tooltip>
        <span className="text-xs text-muted-foreground">
          {column.external_type}
        </span>
      </CommandItem>
      {isExpanded && (
        <div className="pl-10 pr-2 py-2 bg-[var(--slate-1)] shadow-inner border-b">
          <ErrorBoundary>
            <DatasetColumnPreview
              table={table}
              column={column}
              onAddColumnChart={handleAddColumn}
              preview={columnsPreviews.get(`${table.name}:${column.name}`)}
            />
          </ErrorBoundary>
        </div>
      )}
    </>
  );
};

const LazyVegaLite = React.lazy(() =>
  import("react-vega").then((m) => ({ default: m.VegaLite })),
);

const DatasetColumnPreview: React.FC<{
  table: DataTable;
  column: DataTableColumn;
  onAddColumnChart: (code: string) => void;
  preview: DataColumnPreview | undefined;
}> = ({ table, column, preview, onAddColumnChart }) => {
  const { theme } = useTheme();

  // Only fetch previews for local or duckdb tables
  if (table.source_type === "connection") {
    return (
      <span className="text-xs text-muted-foreground gap-2 flex items-center justify-between">
        {column.name} ({column.external_type})
        <Button
          variant="outline"
          size="xs"
          onClick={Events.stopPropagation(() => {
            onAddColumnChart(sqlCode(table, column));
          })}
        >
          <PlusSquareIcon className="h-3 w-3 mr-1" /> Add SQL cell
        </Button>
      </span>
    );
  }

  if (!preview) {
    previewDatasetColumn({
      source: table.source,
      tableName: table.name,
      columnName: column.name,
      sourceType: table.source_type,
    });
  }

  if (!preview) {
    return <span className="text-xs text-muted-foreground">Loading...</span>;
  }

  const error = preview.error && (
    <span className="text-xs text-muted-foreground">{preview.error}</span>
  );

  const summary = preview.summary && (
    <div className="gap-x-16 gap-y-1 grid grid-cols-2-fit border rounded p-2 empty:hidden">
      {Object.entries(preview.summary).map(([key, value]) => {
        if (value == null) {
          return null;
        }

        return (
          <div key={key} className="flex items-center gap-1 group">
            <CopyClipboardIcon
              className="h-3 w-3 invisible group-hover:visible"
              value={String(value)}
            />
            <span className="text-xs min-w-[60px] uppercase">{key}</span>
            <span className="text-xs font-bold text-muted-foreground tracking-wide">
              {prettyNumber(value)}
            </span>
          </div>
        );
      })}
    </div>
  );

  const updateSpec = (spec: TopLevelFacetedUnitSpec) => {
    return {
      ...spec,
      config: { ...spec.config, background: "transparent" },
    };
  };
  const chart = preview.chart_spec && (
    <LazyVegaLite
      spec={updateSpec(
        JSON.parse(preview.chart_spec) as TopLevelFacetedUnitSpec,
      )}
      width={"container" as unknown as number}
      height={100}
      actions={false}
      theme={theme === "dark" ? "dark" : "vox"}
    />
  );

  const addDataframeChart = preview.chart_code &&
    table.source_type === "local" && (
      <Tooltip content="Add chart to notebook" delayDuration={400}>
        <Button
          variant="outline"
          size="icon"
          className="z-10 bg-background absolute right-1 -top-1"
          onClick={Events.stopPropagation(() =>
            onAddColumnChart(preview.chart_code || ""),
          )}
        >
          <PlusSquareIcon className="h-3 w-3" />
        </Button>
      </Tooltip>
    );

  const addSQLChart = table.source_type === "duckdb" && (
    <Tooltip content="Add SQL cell" delayDuration={400}>
      <Button
        variant="outline"
        size="icon"
        className="z-10 bg-background absolute right-1 -top-1"
        onClick={Events.stopPropagation(() => {
          onAddColumnChart(sqlCode(table, column));
        })}
      >
        <PlusSquareIcon className="h-3 w-3" />
      </Button>
    </Tooltip>
  );

  const chartMaxRowsWarning = preview.chart_max_rows_errors && (
    <span className="text-xs text-muted-foreground">
      Too many rows to render the chart.
    </span>
  );

  if (!error && !summary && !chart && !chartMaxRowsWarning) {
    return <span className="text-xs text-muted-foreground">No data</span>;
  }

  return (
    <div className="flex flex-col gap-2 relative">
      {error}
      {addDataframeChart}
      {addSQLChart}
      {chartMaxRowsWarning}
      {chart}
      {summary}
    </div>
  );
};

const DatasourceLabel: React.FC<{
  children: React.ReactNode;
}> = ({ children }) => {
  return (
    <div className="flex gap-1 items-center p-2 font-bold px-2 py-1 text-muted-foreground bg-[var(--slate-2)] text-sm">
      {children}
    </div>
  );
};

const RotatingChevron: React.FC<{ isExpanded: boolean }> = ({ isExpanded }) => (
  <ChevronRightIcon
    className={cn("h-3 w-3 transition-transform", isExpanded && "rotate-90")}
  />
);

export const EmptyState: React.FC<{ content: string; className?: string }> = ({
  content,
  className,
}) => {
  return (
    <div className={cn("text-sm text-muted-foreground py-1", className)}>
      {content}
    </div>
  );
};

function sqlCode(table: DataTable, column: DataTableColumn) {
  if (table.engine) {
    return `_df = mo.sql(f'SELECT "${column.name}" FROM ${table.name} LIMIT 100', engine=${table.engine})`;
  }
  return `_df = mo.sql(f'SELECT "${column.name}" FROM ${table.name} LIMIT 100')`;
}
