/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import {
  DatabaseIcon,
  PlusIcon,
  PaintRollerIcon,
  PlusSquareIcon,
  XIcon,
  Table2Icon,
  EyeIcon,
  RefreshCwIcon,
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
import { atom, useAtomValue, useSetAtom } from "jotai";
import { Tooltip } from "@/components/ui/tooltip";
import { PanelEmptyState } from "../editor/chrome/panels/empty-state";
import {
  previewDataSourceConnection,
  previewDatasetColumn,
} from "@/core/network/requests";
import { prettyNumber } from "@/utils/numbers";
import { Events } from "@/utils/events";
import { CopyClipboardIcon } from "@/components/icons/copy-icon";
import { ErrorBoundary } from "../editor/boundary/ErrorBoundary";
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
  DataSourceConnection,
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
import { AddDatabaseDialog } from "../editor/database/add-database-form";
import {
  dataConnectionsMapAtom,
  DUCKDB_ENGINE,
  INTERNAL_SQL_ENGINES,
  type SQLTableContext,
  useDataSourceActions,
} from "@/core/datasets/data-source-connections";
import { PythonIcon } from "../editor/cell/code/icons";
import { useAsyncData } from "@/hooks/useAsyncData";
import {
  DatasourceLabel,
  EmptyState,
  ErrorState,
  LoadingState,
  RotatingChevron,
} from "./components";
import { InstallPackageButton } from "./install-package-button";
import { isSchemaless, sqlCode } from "./utils";
import { useOnMount } from "@/hooks/useLifecycle";
import {
  PreviewSQLTableList,
  PreviewSQLTable,
} from "@/core/datasets/request-registry";

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

const connectionsAtom = atom((get) => {
  const dataConnections = new Map(get(dataConnectionsMapAtom));

  // Filter out the internal engines if it has no databases
  for (const engine of INTERNAL_SQL_ENGINES) {
    const connection = dataConnections.get(engine);
    if (connection && connection.databases.length === 0) {
      dataConnections.delete(engine);
    }
  }

  // Put internal engines last to prioritize user-defined connections
  return sortBy([...dataConnections.values()], (connection) =>
    INTERNAL_SQL_ENGINES.has(connection.name) ? 1 : 0,
  );
});

export const DataSources: React.FC = () => {
  const [searchValue, setSearchValue] = React.useState<string>("");

  const closeAllColumns = useSetAtom(closeAllColumnsAtom);
  const tables = useAtomValue(sortedTablesAtom);
  const dataConnections = useAtomValue(connectionsAtom);

  if (tables.length === 0 && dataConnections.length === 0) {
    return (
      <PanelEmptyState
        title="No tables found"
        description="Any datasets/dataframes in the global scope will be shown here."
        action={
          <AddDatabaseDialog>
            <Button variant="outline" size="sm">
              Add database or catalog
              <PlusIcon className="h-4 w-4 ml-2" />
            </Button>
          </AddDatabaseDialog>
        }
        icon={<DatabaseIcon />}
      />
    );
  }

  const hasSearch = !!searchValue.trim();

  return (
    <Command
      className="border-b bg-background rounded-none h-full pb-10 overflow-auto outline-none"
      shouldFilter={false}
    >
      <div className="flex items-center w-full">
        <CommandInput
          placeholder="Search tables..."
          className="h-6 m-1"
          value={searchValue}
          onValueChange={(value) => {
            // If searching, remove open previews
            closeAllColumns(value.length > 0);
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

      <CommandList className="flex flex-col">
        {dataConnections.map((connection) => (
          <Engine
            key={connection.name}
            connection={connection}
            hasChildren={connection.databases.length > 0}
          >
            {connection.databases.map((database) => (
              <DatabaseItem
                key={database.name}
                engineName={connection.name}
                database={database}
                hasSearch={hasSearch}
              >
                <SchemaList
                  schemas={database.schemas}
                  defaultSchema={connection.default_schema}
                  defaultDatabase={connection.default_database}
                  engineName={connection.name}
                  databaseName={database.name}
                  hasSearch={hasSearch}
                  searchValue={searchValue}
                />
              </DatabaseItem>
            ))}
          </Engine>
        ))}

        {dataConnections.length > 0 && tables.length > 0 && (
          <DatasourceLabel>
            <PythonIcon className="h-4 w-4 text-muted-foreground" />
            <span className="text-xs">Python</span>
          </DatasourceLabel>
        )}
        {tables.length > 0 && (
          <TableList tables={tables} searchValue={searchValue} />
        )}
      </CommandList>
    </Command>
  );
};

const Engine: React.FC<{
  connection: DataSourceConnection;
  children: React.ReactNode;
  hasChildren?: boolean;
}> = ({ connection, children, hasChildren }) => {
  // The internal duckdb connection is updated automatically, so we do not need to refresh.
  const internalEngine = connection.name === DUCKDB_ENGINE;
  const engineName = internalEngine ? "In-Memory" : connection.name;

  const [isSpinning, setIsSpinning] = React.useState(false);

  const handleRefreshConnection = async () => {
    setIsSpinning(true);
    await previewDataSourceConnection({
      engine: connection.name,
    });
    // Artificially spin the icon if the request is really fast
    setTimeout(() => setIsSpinning(false), 500);
  };

  return (
    <>
      <DatasourceLabel>
        <DatabaseLogo
          className="h-4 w-4 text-muted-foreground"
          name={connection.dialect}
        />
        <span className="text-xs">{dbDisplayName(connection.dialect)}</span>
        <span className="text-xs text-muted-foreground">
          (<EngineVariable variableName={engineName as VariableName} />)
        </span>
        {!internalEngine && (
          <Tooltip content="Refresh connection">
            <Button
              variant="ghost"
              size="icon"
              className="ml-auto hover:bg-transparent hover:shadow-none"
              onClick={handleRefreshConnection}
            >
              <RefreshCwIcon
                className={cn(
                  "h-4 w-4 text-muted-foreground hover:text-foreground",
                  isSpinning && "animate-[spin_0.5s]",
                )}
              />
            </Button>
          </Tooltip>
        )}
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
  hasSearch: boolean;
  engineName: string;
  database: Database;
  children: React.ReactNode;
}> = ({ hasSearch, engineName, database, children }) => {
  const [isExpanded, setIsExpanded] = React.useState(false);
  const [isSelected, setIsSelected] = React.useState(false);

  React.useEffect(() => {
    setIsExpanded(hasSearch);
  }, [hasSearch]);

  return (
    <>
      <CommandItem
        className="text-sm flex flex-row gap-1 items-center cursor-pointer rounded-none"
        onSelect={() => {
          setIsExpanded(!isExpanded);
          setIsSelected(!isSelected);
        }}
        value={`${engineName}:${database.name}`}
      >
        <RotatingChevron isExpanded={isExpanded} />
        <DatabaseIcon
          className={cn(
            "h-4 w-4",
            isSelected && isExpanded
              ? "text-foreground"
              : "text-muted-foreground",
          )}
        />
        <span className={cn(isSelected && isExpanded && "font-semibold")}>
          {database.name === "" ? <i>Not connected</i> : database.name}
        </span>
      </CommandItem>
      {isExpanded && children}
    </>
  );
};

const SchemaList: React.FC<{
  schemas: DatabaseSchema[];
  defaultSchema?: string | null;
  defaultDatabase?: string | null;
  engineName: string;
  databaseName: string;
  hasSearch: boolean;
  searchValue?: string;
}> = ({
  schemas,
  defaultSchema,
  defaultDatabase,
  engineName,
  databaseName,
  hasSearch,
  searchValue,
}) => {
  if (schemas.length === 0) {
    return <EmptyState content="No schemas available" className="pl-6" />;
  }

  const filteredSchemas = schemas.filter((schema) => {
    if (searchValue) {
      return schema.tables.some((table) =>
        table.name.toLowerCase().includes(searchValue.toLowerCase()),
      );
    }
    return true;
  });

  return (
    <>
      {filteredSchemas.map((schema) => (
        <SchemaItem
          key={schema.name}
          databaseName={databaseName}
          schema={schema}
          hasSearch={hasSearch}
        >
          <TableList
            tables={schema.tables}
            searchValue={searchValue}
            sqlTableContext={{
              engine: engineName,
              database: databaseName,
              schema: schema.name,
              defaultSchema: defaultSchema,
              defaultDatabase: defaultDatabase,
            }}
          />
        </SchemaItem>
      ))}
    </>
  );
};

const SchemaItem: React.FC<{
  databaseName: string;
  schema: DatabaseSchema;
  children: React.ReactNode;
  hasSearch: boolean;
}> = ({ databaseName, schema, children, hasSearch }) => {
  const [isExpanded, setIsExpanded] = React.useState(false);
  const [isSelected, setIsSelected] = React.useState(false);
  const uniqueValue = `${databaseName}:${schema.name}`;

  React.useEffect(() => {
    setIsExpanded(hasSearch);
  }, [hasSearch]);

  if (isSchemaless(schema.name)) {
    return children;
  }

  return (
    <>
      <CommandItem
        className="text-sm flex flex-row gap-1 items-center pl-5 cursor-pointer rounded-none"
        onSelect={() => {
          setIsExpanded(!isExpanded);
          setIsSelected(!isSelected);
        }}
        value={uniqueValue}
      >
        <RotatingChevron isExpanded={isExpanded} />
        <PaintRollerIcon
          className={cn(
            "h-4 w-4 text-muted-foreground",
            isSelected && isExpanded && "text-foreground",
          )}
        />
        <span className={cn(isSelected && isExpanded && "font-semibold")}>
          {schema.name}
        </span>
      </CommandItem>
      {isExpanded && children}
    </>
  );
};

const TableList: React.FC<{
  tables: DataTable[];
  sqlTableContext?: SQLTableContext;
  searchValue?: string;
}> = ({ tables, sqlTableContext, searchValue }) => {
  const { addTableList } = useDataSourceActions();
  const [tablesRequested, setTablesRequested] = React.useState(false);

  // Custom loading state, we need to wait for the data to propagate once requested
  // useAsyncData's loading state may return false before data has propagated
  const [tablesLoading, setTablesLoading] = React.useState(false);

  const { loading, error } = useAsyncData(async () => {
    if (tables.length === 0 && sqlTableContext && !tablesRequested) {
      setTablesRequested(true);
      setTablesLoading(true);

      const { engine, database, schema } = sqlTableContext;
      const previewTableList = await PreviewSQLTableList.request({
        engine: engine,
        database: database,
        schema: schema,
      });

      if (!previewTableList?.tables) {
        setTablesLoading(false);
        throw new Error("No tables available");
      }

      addTableList({
        tables: previewTableList.tables,
        sqlTableContext: sqlTableContext,
      });
      setTablesLoading(false);
    }
  }, [tables.length, sqlTableContext, tablesRequested]);

  if (loading || tablesLoading) {
    return <LoadingState message="Loading tables..." />;
  }

  if (error) {
    return <ErrorState error={error} />;
  }

  if (tables.length === 0) {
    return <EmptyState content="No tables found" className="pl-9" />;
  }

  const filteredTables = tables.filter((table) => {
    if (searchValue) {
      return table.name.toLowerCase().includes(searchValue.toLowerCase());
    }
    return true;
  });

  return (
    <>
      {filteredTables.map((table) => (
        <DatasetTableItem
          key={table.name}
          table={table}
          sqlTableContext={sqlTableContext}
          isSearching={!!searchValue}
        />
      ))}
    </>
  );
};

const DatasetTableItem: React.FC<{
  table: DataTable;
  sqlTableContext?: SQLTableContext;
  isSearching: boolean;
}> = ({ table, sqlTableContext, isSearching }) => {
  const { addTable } = useDataSourceActions();

  const [isExpanded, setIsExpanded] = React.useState(false);
  const [tableDetailsRequested, setTableDetailsRequested] =
    React.useState(false);
  const tableDetailsExist = table.columns.length > 0;

  const { loading, error } = useAsyncData(async () => {
    if (
      isExpanded &&
      !tableDetailsExist &&
      sqlTableContext &&
      !tableDetailsRequested
    ) {
      setTableDetailsRequested(true);
      const { engine, database, schema } = sqlTableContext;
      const previewTable = await PreviewSQLTable.request({
        engine: engine,
        database: database,
        schema: schema,
        tableName: table.name,
      });

      if (!previewTable?.table) {
        throw new Error("No table details available");
      }

      addTable({
        table: previewTable.table,
        sqlTableContext: sqlTableContext,
      });
    }
  }, [isExpanded, tableDetailsExist]);

  const autoInstantiate = useAtomValue(autoInstantiateAtom);
  const lastFocusedCellId = useLastFocusedCellId();
  const { createNewCell } = useCellActions();

  const handleAddTable = () => {
    maybeAddMarimoImport(autoInstantiate, createNewCell, lastFocusedCellId);
    const getCode = () => {
      if (table.source_type === "catalog") {
        const identifier = sqlTableContext?.database
          ? `${sqlTableContext.database}.${table.name}`
          : table.name;
        return `${table.engine}.load_table("${identifier}")`;
      }

      if (sqlTableContext) {
        return sqlCode(table, "*", sqlTableContext);
      }

      switch (table.source_type) {
        case "local":
          return `mo.ui.table(${table.name})`;
        case "duckdb":
        case "connection":
          return sqlCode(table, "*", sqlTableContext);
        default:
          logNever(table.source_type);
          return "";
      }
    };

    createNewCell({
      code: getCode(),
      before: false,
      cellId: lastFocusedCellId ?? "__end__",
    });
  };

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
      return <LoadingState message="Loading columns..." />;
    }

    if (error) {
      return <ErrorState error={error} />;
    }

    const columns = table.columns;
    return columns.map((column) => (
      <DatasetColumnItem
        key={column.name}
        table={table}
        column={column}
        sqlTableContext={sqlTableContext}
      />
    ));
  };

  const renderTableType = () => {
    if (table.source_type === "local") {
      return;
    }

    const TableTypeIcon = table.type === "table" ? Table2Icon : EyeIcon;
    return (
      <TableTypeIcon
        className="h-3 w-3"
        strokeWidth={isExpanded || isSearching ? 2.5 : undefined}
      />
    );
  };

  const uniqueId = sqlTableContext
    ? `${sqlTableContext.database}.${sqlTableContext.schema}.${table.name}`
    : table.name;

  return (
    <>
      <CommandItem
        className={cn(
          "rounded-none group h-8 cursor-pointer",
          sqlTableContext &&
            (isSchemaless(sqlTableContext.schema) ? "pl-9" : "pl-12"),
          (isExpanded || isSearching) && "font-semibold",
        )}
        value={uniqueId}
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
            onClick={Events.stopPropagation(() => handleAddTable())}
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
  sqlTableContext?: SQLTableContext;
}> = ({ table, column, sqlTableContext }) => {
  const [isExpanded, setIsExpanded] = React.useState(false);
  const closeAllColumns = useAtomValue(closeAllColumnsAtom);
  const setExpandedColumns = useSetAtom(expandedColumnsAtom);

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
  const isPrimaryKey = table.primary_keys?.includes(column.name) || false;
  const isIndexed = table.indexes?.includes(column.name) || false;

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

  const renderItemSubtext = ({
    tooltipContent,
    content,
  }: {
    tooltipContent: string;
    content: string;
  }) => {
    return (
      <Tooltip content={tooltipContent} delayDuration={100}>
        <span className="text-xs text-black bg-gray-100 dark:invert rounded px-1">
          {content}
        </span>
      </Tooltip>
    );
  };

  return (
    <>
      <CommandItem
        className="rounded-none py-1 group cursor-pointer"
        key={`${table.name}.${column.name}`}
        value={`${table.name}.${column.name}`}
        onSelect={() => setIsExpanded(!isExpanded)}
      >
        <div
          className={cn(
            "flex flex-row gap-2 items-center flex-1",
            sqlTableContext ? "pl-14" : "pl-7",
          )}
        >
          <Icon className="flex-shrink-0 h-3 w-3" strokeWidth={1.5} />
          <span>{column.name}</span>
          {isPrimaryKey &&
            renderItemSubtext({ tooltipContent: "Primary key", content: "PK" })}
          {isIndexed &&
            renderItemSubtext({ tooltipContent: "Indexed", content: "IDX" })}
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
              preview={columnsPreviews.get(
                sqlTableContext
                  ? `${sqlTableContext.database}.${sqlTableContext.schema}.${table.name}:${column.name}`
                  : `${table.name}:${column.name}`,
              )}
              sqlTableContext={sqlTableContext}
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
  sqlTableContext?: SQLTableContext;
}> = ({ table, column, preview, onAddColumnChart, sqlTableContext }) => {
  const { theme } = useTheme();

  useOnMount(() => {
    if (preview) {
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

  // Do not fetch previews for custom SQL connections
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

  const error = preview.error && (
    <div className="text-xs text-muted-foreground p-2 border border-muted rounded flex items-center">
      <span>{preview.error}</span>
      {preview.missing_packages && (
        <InstallPackageButton packages={preview.missing_packages} />
      )}
    </div>
  );

  const stats = preview.stats && (
    <div className="gap-x-16 gap-y-1 grid grid-cols-2-fit border rounded p-2 empty:hidden">
      {Object.entries(preview.stats).map(([key, value]) => {
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
          onAddColumnChart(sqlCode(table, column.name, sqlTableContext));
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

  if (!error && !stats && !chart && !chartMaxRowsWarning) {
    return <span className="text-xs text-muted-foreground">No data</span>;
  }

  return (
    <div className="flex flex-col gap-2 relative">
      {error}
      {addDataframeChart}
      {addSQLChart}
      {chartMaxRowsWarning}
      {chart}
      {stats}
    </div>
  );
};
