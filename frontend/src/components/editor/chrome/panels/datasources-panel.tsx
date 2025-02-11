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
} from "lucide-react";
import { Command, CommandInput, CommandItem } from "@/components/ui/command";
import { CommandList } from "cmdk";

import { cn } from "@/utils/cn";
import {
  datasetTablesAtom,
  useDatasets,
  useDatasetsActions,
} from "@/core/datasets/state";
import { DATA_TYPE_ICON } from "@/components/datasets/icons";
import { Button } from "@/components/ui/button";
import { cellIdsAtom, useCellActions } from "@/core/cells/cells";
import { useLastFocusedCellId } from "@/core/cells/focus";
import { atom, useAtomValue } from "jotai";
import { Tooltip } from "@/components/ui/tooltip";
import { PanelEmptyState } from "./empty-state";
import { previewDatasetColumn } from "@/core/network/requests";
import type { ColumnPreviewMap } from "@/core/datasets/types";
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
import { Objects } from "@/utils/objects";
import { DatabaseLogo } from "@/components/databases/icon";
import { EngineVariable } from "@/components/databases/engine-variable";
import type { VariableName } from "@/core/variables/types";
import { dbDisplayName } from "@/components/databases/display";
import { AddDatabaseDialog } from "../../database/add-database-form";
import { databasesAtom, type DatabaseState } from "@/core/datasets/databases";
import { PythonIcon } from "../../cell/code/icons";
import { DEFAULT_ENGINE } from "@/core/datasets/data-source-connections";
import { PreviewSQLTables } from "@/core/functions/FunctionRegistry";

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
  const { expandedColumns, expandedTables, columnsPreviews } = useDatasets();
  const { toggleTable, toggleColumn, closeAllColumns } = useDatasetsActions();
  const { createNewCell } = useCellActions();
  const tables = useAtomValue(sortedTablesAtom);
  const databases = useAtomValue(databasesAtom);

  if (tables.length === 0) {
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
              closeAllColumns();
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

      <EngineList databasesMap={databases.databasesMap} />

      <DatasourceLabel>
        <PythonIcon className="h-4 w-4 text-muted-foreground" />
        <span>Python</span>
      </DatasourceLabel>
      <TableList
        onAddColumnChart={handleAddColumn}
        onAddTable={handleAddTable}
        onExpandColumn={(table, column) => {
          const tableColumn = `${table.name}:${column.name}` as const;
          toggleColumn({
            table: table.name,
            column: column.name,
          });
          if (!columnsPreviews.has(tableColumn)) {
            previewDatasetColumn({
              source: table.source,
              tableName: table.name,
              columnName: column.name,
              sourceType: table.source_type,
            });
          }
        }}
        onExpandTable={(table) => {
          toggleTable(table.name);
        }}
        columnPreviews={columnsPreviews}
        tables={tables}
        isSearching={hasSearch}
        isTableExpanded={(table) => {
          // Always show tables if there is a search value
          if (hasSearch) {
            return true;
          }
          return expandedTables.has(table.name);
        }}
        isColumnExpanded={(table, column) => {
          const tableColumn = `${table.name}:${column.name}` as const;
          return expandedColumns.has(tableColumn);
        }}
      />
    </Command>
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

const EngineList: React.FC<{ databasesMap: DatabaseState["databasesMap"] }> = ({
  databasesMap,
}) => {
  const groupedByEngine = Object.entries(
    Object.groupBy(
      [...databasesMap.values()],
      (database) => database.engine || DEFAULT_ENGINE,
    ),
  );

  return (
    <>
      {groupedByEngine.map(([engine, databases]) => {
        const source = databases?.[0].dialect || "duckdb";

        return (
          <div key={engine}>
            <DatasourceLabel>
              <DatabaseLogo
                className="h-4 w-4 text-muted-foreground"
                name={source}
              />
              <span>{dbDisplayName(source)}</span>
              <span className="text-xs text-muted-foreground">
                (<EngineVariable variableName={engine as VariableName} />)
              </span>
            </DatasourceLabel>
            {databases && databases.length > 0 ? (
              databases.map((database) => (
                <DatabaseItem
                  key={database.name}
                  database={database}
                  engineName={engine}
                />
              ))
            ) : (
              <span className="text-sm text-muted-foreground p-2">
                No databases available
              </span>
            )}
          </div>
        );
      })}
    </>
  );
};

const DatabaseItem: React.FC<{ database: Database; engineName: string }> = ({
  database,
  engineName,
}) => {
  const [isExpanded, setIsExpanded] = React.useState(false);

  return (
    <>
      <CommandItem
        key={database.name}
        className="text-sm flex flex-row gap-1 items-center border-b cursor-pointer"
        onSelect={() => setIsExpanded(!isExpanded)}
      >
        <RotatingChevron isExpanded={isExpanded} />
        <DatabaseIcon className="h-4 w-4 text-muted-foreground" />
        {database.name}
      </CommandItem>
      {isExpanded &&
        Object.values(database.schemas).map((schema) => (
          <SchemaItem
            key={schema.name}
            schema={schema}
            engineName={engineName}
            databaseName={database.name}
          />
        ))}
    </>
  );
};

const SchemaItem: React.FC<{
  schema: DatabaseSchema;
  engineName: string;
  databaseName: string;
}> = ({ schema, engineName, databaseName }) => {
  const [isExpanded, setIsExpanded] = React.useState(false);
  return (
    <>
      <CommandItem
        key={schema.name}
        className="py-1 text-sm flex flex-row gap-1 items-center border-b ml-5 cursor-pointer"
        onSelect={() => setIsExpanded(!isExpanded)}
      >
        <RotatingChevron isExpanded={isExpanded} />
        <PaintRollerIcon className="h-4 w-4 text-muted-foreground" />
        {schema.name}
      </CommandItem>
      {isExpanded && (
        <EngineTableList
          tables={Object.values(schema.tables)}
          engineName={engineName}
          databaseName={databaseName}
          schemaName={schema.name}
        />
      )}
    </>
  );
};

interface EngineTableListProps {
  engineName: string;
  databaseName: string;
  schemaName: string;
  tables: DataTable[];
}

const EngineTableList: React.FC<EngineTableListProps> = ({
  engineName,
  databaseName,
  schemaName,
  tables,
}) => {
  const [data, setData] = React.useState<DataTable[]>(tables);
  const [loading, setLoading] = React.useState<boolean>(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let isMounted = true;

    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const tablesPreview = await PreviewSQLTables.request({
          schema: schemaName,
          engine: engineName,
          database: databaseName,
        });
        if (tablesPreview.error) {
          throw new Error(tablesPreview.error);
        }
        if (isMounted) {
          setData(tablesPreview.tables);
        }
      } catch (error) {
        if (isMounted) {
          if (error instanceof Error) {
            setError(error.message);
          } else {
            setError(String(error));
          }
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    // Only fetch when no tables are passed in
    if (tables.length === 0) {
      fetchData();
    }

    return () => {
      isMounted = false;
    };
  }, [databaseName, engineName, schemaName, tables.length]);

  if (error) {
    return (
      <div className="ml-8 text-sm text-red-600 bg-red-100 flex items-center gap-2 p-2 h-7 overflow-auto">
        <XIcon className="h-4 w-4" />
        Internal error: {error}
      </div>
    );
  }

  if (loading) {
    return (
      <div className="ml-8 text-sm bg-blue-50 text-blue-600 flex items-center gap-2 p-2 h-7">
        <LoaderCircle className="h-4 w-4 animate-spin" />
        Loading...
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="ml-8 text-sm text-muted-foreground p-2">
        No tables found
      </div>
    );
  }

  return (
    <div className="ml-8">
      <TableList
        tables={data}
        isSearching={false}
        columnPreviews={new Map()}
        onAddColumnChart={() => {}}
        onAddTable={() => {}}
        onExpandTable={() => {}}
        onExpandColumn={() => {}}
        isTableExpanded={() => false}
        isColumnExpanded={() => false}
      />
    </div>
  );
};

const TableList: React.FC<{
  onAddColumnChart: (chartCode: string) => void;
  onAddTable: (table: DataTable) => void;
  onExpandTable: (table: DataTable) => void;
  onExpandColumn: (table: DataTable, column: DataTableColumn) => void;
  isTableExpanded: (table: DataTable) => boolean;
  isColumnExpanded: (table: DataTable, column: DataTableColumn) => boolean;
  columnPreviews: ColumnPreviewMap;
  isSearching: boolean;
  tables: DataTable[];
}> = ({
  tables,
  isSearching,
  columnPreviews,
  onAddColumnChart,
  onAddTable,
  onExpandTable,
  onExpandColumn,
  isTableExpanded,
  isColumnExpanded,
}) => {
  // Tables grouped by engine (if exists) or source
  // The engine is a more specific source, so it should be grouped first
  let groupedBySource = Object.entries(
    Objects.groupBy(
      tables,
      (table) => table.engine || table.source,
      (table) => table,
    ),
  );
  // Sort by `memory` first, then by alphabet
  groupedBySource = sortBy(groupedBySource, ([source]) => {
    if (source === "memory") {
      return 0;
    }
    return 1;
  });

  const renderTable = (table: DataTable): React.ReactNode => {
    const expanded = isTableExpanded(table);
    const items = [
      <DatasetTableItem
        key={table.name}
        table={table}
        forceMount={isSearching}
        onExpand={() => onExpandTable(table)}
        onAddTable={() => onAddTable(table)}
        isExpanded={expanded}
      />,
    ];

    if (expanded) {
      items.push(
        ...table.columns.map((column) => {
          return (
            <React.Fragment key={`${table.name}.${column.name}`}>
              <DatasetColumnItem
                key={`${table.name}.${column.name}`}
                table={table}
                column={column}
                onExpandColumn={onExpandColumn}
                isExpanded={isColumnExpanded(table, column)}
              />
              {isColumnExpanded(table, column) && (
                <div className="pl-10 pr-2 py-2 bg-[var(--slate-1)] shadow-inner border-b">
                  <ErrorBoundary>
                    <DatasetColumnPreview
                      table={table}
                      column={column}
                      onAddColumnChart={onAddColumnChart}
                      preview={columnPreviews.get(
                        `${table.name}:${column.name}`,
                      )}
                    />
                  </ErrorBoundary>
                </div>
              )}
            </React.Fragment>
          );
        }),
      );
    }

    return items;
  };

  const renderTableWithHeaders = () => {
    if (groupedBySource.length === 0) {
      return null;
    }
    if (groupedBySource.length === 1) {
      return groupedBySource[0][1].flatMap(renderTable);
    }

    const renderLabel = (source: string, tables: DataTable[]) => {
      if (source === "memory") {
        return "In-Memory";
      }

      if (source === "duckdb") {
        return "DuckDB";
      }

      const firstTable = tables[0];
      if (firstTable.engine) {
        return (
          <>
            <DatabaseLogo
              className="h-4 w-4 text-muted-foreground"
              name={firstTable.source}
            />
            {dbDisplayName(firstTable.source)}
            <span className="text-xs text-muted-foreground">
              (
              <EngineVariable
                variableName={firstTable.engine as VariableName}
              />
              )
            </span>
          </>
        );
      }
      return source;
    };

    return groupedBySource.flatMap(([source, tables], idx) => {
      return [
        <div
          className={cn(
            "font-bold px-2 py-1 text-muted-foreground bg-[var(--slate-2)] border-t text-sm flex items-center gap-1",
            idx > 0 && "border-t",
          )}
          key={source}
        >
          {renderLabel(source, tables)}
        </div>,
        ...tables.flatMap(renderTable),
      ];
    });
  };

  return (
    <CommandList className="flex flex-col overflow-auto">
      {renderTableWithHeaders()}
    </CommandList>
  );
};

const DatasetTableItem: React.FC<{
  table: DataTable;
  onExpand: () => void;
  forceMount?: boolean;
  onAddTable: (table: DataTable) => void;
  isExpanded: boolean;
}> = ({ table, onExpand, onAddTable, isExpanded }) => {
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

  return (
    <CommandItem
      className="rounded-none py-1 group h-7 border-t cursor-pointer"
      value={table.name}
      aria-selected={isExpanded}
      forceMount={true}
      onSelect={onExpand}
    >
      <div className="flex gap-1 items-center flex-1">
        <RotatingChevron isExpanded={isExpanded} />
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
  );
};

const DatasetColumnItem: React.FC<{
  table: DataTable;
  column: DataTableColumn;
  onExpandColumn: (table: DataTable, column: DataTableColumn) => void;
  isExpanded: boolean;
}> = ({ table, column, onExpandColumn }) => {
  const Icon = DATA_TYPE_ICON[column.type];

  return (
    <CommandItem
      className="rounded-none py-1 group cursor-pointer"
      key={`${table.name}.${column.name}`}
      value={`${table.name}.${column.name}`}
      onSelect={() => onExpandColumn(table, column)}
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

function sqlCode(table: DataTable, column: DataTableColumn) {
  if (table.engine) {
    return `_df = mo.sql(f'SELECT "${column.name}" FROM ${table.name} LIMIT 100', engine=${table.engine})`;
  }
  return `_df = mo.sql(f'SELECT "${column.name}" FROM ${table.name} LIMIT 100')`;
}
