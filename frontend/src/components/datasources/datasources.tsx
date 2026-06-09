/* Copyright 2026 Marimo. All rights reserved. */

import { CommandList } from "cmdk";
import { atom, useAtom, useAtomValue, useSetAtom } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { PlusIcon, PlusSquareIcon, XIcon } from "lucide-react";
import React from "react";
import { dbDisplayName } from "@/components/databases/display";
import { EngineVariable } from "@/components/databases/engine-variable";
import { DatabaseLogo } from "@/components/databases/icon";
import {
  RefreshIconButton,
  VisibilityToggleButton,
} from "@/components/editor/file-tree/tree-actions";
import { CopyClipboardIcon } from "@/components/icons/copy-icon";
import { Button } from "@/components/ui/button";
import { Command, CommandInput, CommandItem } from "@/components/ui/command";
import { Tooltip } from "@/components/ui/tooltip";
import { maybeAddMarimoImport } from "@/core/cells/add-missing-import";
import { cellIdsAtom, useCellActions } from "@/core/cells/cells";
import { useLastFocusedCellId } from "@/core/cells/focus";
import { autoInstantiateAtom } from "@/core/config/config";
import {
  dataConnectionsMapAtom,
  type SQLTableContext,
  useDataSourceActions,
} from "@/core/datasets/data-source-connections";
import {
  DEFAULT_DUCKDB_DATABASE,
  DUCKDB_ENGINE,
  INTERNAL_SQL_ENGINES,
} from "@/core/datasets/engines";
import {
  PreviewSQLSchemaList,
  PreviewSQLTable,
  PreviewSQLTableList,
} from "@/core/datasets/request-registry";
import {
  closeAllColumnsAtom,
  datasetTablesAtom,
  expandedColumnsAtom,
  useDatasets,
} from "@/core/datasets/state";
import type {
  Database,
  DatabaseSchema,
  DataSourceConnection,
  DataTable,
  DataTableColumn,
} from "@/core/kernel/messages";
import { useRequestClient } from "@/core/network/requests";
import { variablesAtom } from "@/core/variables/state";
import type { VariableName } from "@/core/variables/types";
import { useAsyncData } from "@/hooks/useAsyncData";
import { sortBy } from "@/utils/arrays";
import { logNever } from "@/utils/assertNever";
import { cn } from "@/utils/cn";
import { Events } from "@/utils/events";
import { jotaiJsonStorage } from "@/utils/storage/jotai";
import {
  DatabaseIcon,
  SchemaIcon,
  TableIcon,
  ViewIcon,
} from "../databases/namespace-icons";
import { ErrorBoundary } from "../editor/boundary/ErrorBoundary";
import { PythonIcon } from "../editor/cell/code/icons";
import { useAddCodeToNewCell } from "../editor/cell/useAddCell";
import { PanelEmptyState } from "../editor/chrome/panels/empty-state";
import { AddConnectionDialog } from "../editor/connections/add-connection-dialog";
import { DatasetColumnPreview } from "./column-preview";
import {
  ColumnName,
  DatasourceLabel,
  EmptyState,
  ErrorState,
  LoadingState,
  RotatingChevron,
} from "./components";
import { isSchemaless, sqlCode } from "./utils";

// Indentation classes for the datasource tree hierarchy.
const INDENT = {
  engineEmpty: "pl-3",
  engine: "pl-3 pr-2",
  database: "pl-4",
  schemaEmpty: "pl-8",
  schema: "pl-7",
  schemaLoading: "pl-8",
  tableLoading: "pl-11",
  tableSchemaless: "pl-8",
  tableWithSchema: "pl-12",
  columnLocal: "pl-5",
  columnSql: "pl-13",
  columnPreview: "pl-10",
};

// Indentation (rem) for nested namespace levels, by nesting depth. Calibrated
// so depth 0 matches the fixed pl-7 / pl-12 / pl-13 classes.
function namespaceHeaderIndentRem(depth: number): number {
  return 1.75 + depth;
}
function namespaceTableIndentRem(depth: number): number {
  return 3 + depth;
}
function namespaceColumnIndentRem(depth: number): number {
  return 3.25 + depth;
}

// Indent a transient loading/error/empty row: inline padding when nested,
// else a fixed class.
function stateIndentProps(
  rem: number | undefined,
  fallbackClassName: string,
): { className: string } | { style: React.CSSProperties } {
  return rem == null
    ? { className: fallbackClassName }
    : { style: { paddingLeft: `${rem}rem` } };
}

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

/**
 * Whether to hide empty schemas and databases (those with no tables) in the
 * datasources panel.
 */
export const hideEmptyDatasourcesAtom = atomWithStorage<boolean>(
  "marimo:datasources:hideEmpty",
  false,
  jotaiJsonStorage,
  { getOnInit: true },
);

/**
 * Recursively hide schemas confirmed empty (no tables and no visible child
 * namespaces). Deferred schemas are kept so the user can expand them.
 */
function filterEmptySchemas(schemas: DatabaseSchema[]): DatabaseSchema[] {
  let changed = false;
  const result: DatabaseSchema[] = [];
  for (const schema of schemas) {
    if (schema.tables_resolved === false || schema.schemas_resolved === false) {
      result.push(schema);
      continue;
    }
    const childSchemas = schema.schemas ?? [];
    const visibleChildren = filterEmptySchemas(childSchemas);
    if (schema.tables.length === 0 && visibleChildren.length === 0) {
      changed = true;
      continue;
    }
    if (visibleChildren === childSchemas) {
      result.push(schema);
      continue;
    }
    changed = true;
    result.push({ ...schema, schemas: visibleChildren });
  }
  return changed ? result : schemas;
}

/**
 * Apply the "hide empty" filter to a connection's databases.
 *
 * - Schemas with confirmed-empty table lists (and no child namespaces) are
 *   hidden, recursively.
 * - Databases are hidden when either (a) their schemas have been enumerated
 *   and the list is empty, or (b) every schema in them was hidden by the
 *   schema-level filter.
 * - Databases / schemas whose contents haven't been resolved yet (deferred
 *   discovery — `schemas_resolved === false` or `tables_resolved === false`)
 *   are preserved so the user can expand them to trigger a fetch.
 */
export function filterEmptyDatabases(databases: Database[]): Database[] {
  let changed = false;
  const result: Database[] = [];
  for (const database of databases) {
    // Known-empty database: schema list was enumerated and is empty.
    if (database.schemas_resolved !== false && database.schemas.length === 0) {
      changed = true;
      continue;
    }
    // Deferred schema discovery — keep so the user can expand and load.
    if (database.schemas.length === 0) {
      result.push(database);
      continue;
    }
    const visibleSchemas = filterEmptySchemas(database.schemas);
    if (visibleSchemas.length === 0) {
      changed = true;
      continue;
    }
    if (visibleSchemas === database.schemas) {
      result.push(database);
      continue;
    }
    changed = true;
    result.push({ ...database, schemas: visibleSchemas });
  }
  return changed ? result : databases;
}

/**
 * This atom is used to get the data connections that are available to the user.
 * It filters out the internal engines if it has no databases or if it has only the in-memory database and no schemas.
 */
export const connectionsAtom = atom((get) => {
  const dataConnections = new Map(get(dataConnectionsMapAtom));

  // Filter out the internal engines if it has no databases
  // Or if it has only the in-memory database and no schemas
  for (const engine of INTERNAL_SQL_ENGINES) {
    const connection = dataConnections.get(engine);
    if (!connection) {
      continue;
    }

    if (connection.databases.length === 0) {
      dataConnections.delete(engine);
    }

    if (
      connection.databases.length === 1 &&
      connection.databases[0].name === DEFAULT_DUCKDB_DATABASE &&
      connection.databases[0].schemas.length === 0
    ) {
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
  const [hideEmpty, setHideEmpty] = useAtom(hideEmptyDatasourcesAtom);

  const closeAllColumns = useSetAtom(closeAllColumnsAtom);
  const tables = useAtomValue(sortedTablesAtom);
  const rawConnections = useAtomValue(connectionsAtom);

  const dataConnections = React.useMemo(() => {
    if (!hideEmpty) {
      return rawConnections;
    }
    let changed = false;
    const filtered = rawConnections.map((connection) => {
      const databases = filterEmptyDatabases(connection.databases);
      if (databases === connection.databases) {
        return connection;
      }
      changed = true;
      return { ...connection, databases };
    });
    return changed ? filtered : rawConnections;
  }, [rawConnections, hideEmpty]);

  if (tables.length === 0 && dataConnections.length === 0) {
    return (
      <PanelEmptyState
        title="No tables found"
        description="Any datasets/dataframes in the global scope will be shown here."
        action={
          <AddConnectionDialog>
            <Button variant="outline" size="sm">
              Add database or catalog
              <PlusIcon className="h-4 w-4 ml-2" />
            </Button>
          </AddConnectionDialog>
        }
        icon={<DatabaseIcon />}
      />
    );
  }

  const hasSearch = !!searchValue.trim();

  return (
    <Command
      className="border-b bg-background rounded-none h-full pb-10 overflow-auto outline-hidden"
      shouldFilter={false}
    >
      <div className="flex items-center w-full border-b">
        <CommandInput
          placeholder="Search tables..."
          className="h-6 m-1"
          value={searchValue}
          onValueChange={(value) => {
            // If searching, remove open previews
            closeAllColumns(value.length > 0);
            setSearchValue(value);
          }}
          rootClassName="flex-1 border-r border-b-0"
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

        <VisibilityToggleButton
          data-testid="datasources-hide-empty-button"
          isVisible={!hideEmpty}
          onToggle={() => setHideEmpty(!hideEmpty)}
          showTooltip="Show empty schemas and databases"
          hideTooltip="Hide empty schemas and databases"
          size="sm"
          className="px-2 rounded-none focus-visible:outline-hidden"
        />

        <AddConnectionDialog>
          <Button
            variant="ghost"
            size="sm"
            className="px-2 rounded-none focus-visible:outline-hidden"
          >
            <PlusIcon className="h-4 w-4" />
          </Button>
        </AddConnectionDialog>
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
                  schemasResolved={database.schemas_resolved !== false}
                  namespacePath={[]}
                  depth={0}
                  defaultSchema={connection.default_schema}
                  defaultDatabase={connection.default_database}
                  engineName={connection.name}
                  databaseName={database.name}
                  hasSearch={hasSearch}
                  searchValue={searchValue}
                  dialect={connection.dialect}
                />
              </DatabaseItem>
            ))}
          </Engine>
        ))}

        {dataConnections.length > 0 && tables.length > 0 && (
          <DatasourceLabel className={INDENT.engine}>
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
  const { previewDataSourceConnection } = useRequestClient();

  const handleRefreshConnection = async () => {
    await previewDataSourceConnection({
      engine: connection.name,
    });
  };

  return (
    <>
      <DatasourceLabel className={INDENT.engine}>
        <DatabaseLogo
          className="h-4 w-4 text-muted-foreground"
          name={connection.dialect}
        />
        <span className="text-xs">{dbDisplayName(connection.dialect)}</span>
        <span className="text-xs text-muted-foreground">
          (<EngineVariable variableName={engineName as VariableName} />)
        </span>
        {!internalEngine && (
          <RefreshIconButton
            onClick={handleRefreshConnection}
            tooltip="Refresh connection"
            className="ml-auto h-4 p-0"
            iconClassName="h-3.5 w-3.5"
          />
        )}
      </DatasourceLabel>
      {hasChildren ? (
        children
      ) : (
        <EmptyState
          content="No databases available"
          className={INDENT.engineEmpty}
        />
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
  const [prevHasSearch, setPrevHasSearch] = React.useState(hasSearch);

  if (prevHasSearch !== hasSearch) {
    setPrevHasSearch(hasSearch);
    setIsExpanded(hasSearch);
  }

  return (
    <>
      <CommandItem
        className={cn(
          "text-sm flex flex-row gap-1 items-center cursor-pointer rounded-none",
          INDENT.database,
        )}
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

interface SchemaListContext {
  defaultSchema?: string | null;
  defaultDatabase?: string | null;
  dialect: string;
  engineName: string;
  databaseName: string;
  hasSearch: boolean;
  searchValue?: string;
}

const SchemaList: React.FC<
  SchemaListContext & {
    schemas: DatabaseSchema[];
    // Whether `schemas` has been enumerated; when false, discovery is deferred
    // and a request is issued on mount (i.e. when the parent is expanded).
    schemasResolved: boolean;
    // Parent namespace path (relative to the database) of these schemas. Empty
    // for the database's top-level schemas.
    namespacePath: string[];
    // Nesting depth of these schemas (0 = top-level).
    depth: number;
  }
> = (props) => {
  const {
    schemas,
    schemasResolved,
    namespacePath,
    depth,
    defaultSchema,
    defaultDatabase,
    dialect,
    engineName,
    databaseName,
    hasSearch,
    searchValue,
  } = props;
  const { addSchemaList } = useDataSourceActions();
  const [schemasRequested, setSchemasRequested] = React.useState(false);

  // Custom loading state, we need to wait for the data to propagate once requested
  // useAsyncData's loading state may return false before data has propagated
  const [schemasLoading, setSchemasLoading] = React.useState(false);
  const namespaceKey = namespacePath.join(" ");

  const { isPending, error } = useAsyncData(async () => {
    if (!schemasResolved && engineName && !schemasRequested) {
      setSchemasRequested(true);
      setSchemasLoading(true);
      try {
        const previewSchemaList = await PreviewSQLSchemaList.request({
          engine: engineName,
          database: databaseName,
          namespacePath: namespacePath,
        });

        addSchemaList({
          schemas: previewSchemaList.schemas ?? [],
          sqlSchemaContext: {
            engine: engineName,
            database: databaseName,
            namespacePath: namespacePath,
          },
        });
      } finally {
        setSchemasLoading(false);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    schemasResolved,
    engineName,
    databaseName,
    namespaceKey,
    schemasRequested,
  ]);

  if (isPending || schemasLoading) {
    return (
      <LoadingState
        message="Loading schemas..."
        className={INDENT.schemaLoading}
      />
    );
  }

  if (error) {
    return <ErrorState error={error} className={INDENT.schemaLoading} />;
  }

  if (schemas.length === 0) {
    return (
      <EmptyState
        content="No schemas available"
        className={INDENT.schemaEmpty}
      />
    );
  }

  const context: SchemaListContext = {
    defaultSchema,
    defaultDatabase,
    dialect,
    engineName,
    databaseName,
    hasSearch,
    searchValue,
  };

  return (
    <>
      {schemas.map((schema) => {
        // Schemaless namespaces (the database's own tables) render their tables
        // directly under the database with no expandable node.
        if (isSchemaless(schema.name)) {
          return (
            <TableList
              key={schema.name}
              tables={schema.tables}
              tablesResolved={schema.tables_resolved !== false}
              searchValue={searchValue}
              sqlTableContext={{
                engine: engineName,
                database: databaseName,
                schema: schema.name,
                namespacePath: namespacePath,
                defaultSchema: defaultSchema,
                defaultDatabase: defaultDatabase,
                dialect: dialect,
              }}
            />
          );
        }
        return (
          <NamespaceNode
            key={schema.name}
            schema={schema}
            namespacePath={[...namespacePath, schema.name]}
            depth={depth}
            {...context}
          />
        );
      })}
    </>
  );
};

const NamespaceNode: React.FC<
  SchemaListContext & {
    schema: DatabaseSchema;
    // Path of this namespace relative to the database (includes this node).
    namespacePath: string[];
    depth: number;
  }
> = (props) => {
  const {
    schema,
    namespacePath,
    depth,
    engineName,
    databaseName,
    defaultSchema,
    defaultDatabase,
    dialect,
    hasSearch,
    searchValue,
  } = props;
  const [isExpanded, setIsExpanded] = React.useState(hasSearch);
  const [isSelected, setIsSelected] = React.useState(false);
  const uniqueValue = `${databaseName}:${namespacePath.join(".")}`;
  const childSchemas = schema.schemas ?? [];

  return (
    <>
      <CommandItem
        className="text-sm flex flex-row gap-1 items-center cursor-pointer rounded-none"
        style={{ paddingLeft: `${namespaceHeaderIndentRem(depth)}rem` }}
        onSelect={() => {
          setIsExpanded(!isExpanded);
          setIsSelected(!isSelected);
        }}
        value={uniqueValue}
      >
        <RotatingChevron isExpanded={isExpanded} />
        <SchemaIcon
          className={cn(
            "h-4 w-4 text-muted-foreground",
            isSelected && isExpanded && "text-foreground",
          )}
        />
        <span className={cn(isSelected && isExpanded && "font-semibold")}>
          {schema.name}
        </span>
      </CommandItem>
      {isExpanded && (
        <>
          {/* Nested child namespaces */}
          {(childSchemas.length > 0 || schema.schemas_resolved === false) && (
            <SchemaList
              schemas={childSchemas}
              schemasResolved={schema.schemas_resolved !== false}
              namespacePath={namespacePath}
              depth={depth + 1}
              engineName={engineName}
              databaseName={databaseName}
              defaultSchema={defaultSchema}
              defaultDatabase={defaultDatabase}
              dialect={dialect}
              hasSearch={hasSearch}
              searchValue={searchValue}
            />
          )}
          {/* Tables that live directly in this namespace */}
          <TableList
            tables={schema.tables}
            tablesResolved={schema.tables_resolved !== false}
            searchValue={searchValue}
            tableIndentRem={namespaceTableIndentRem(depth)}
            columnIndentRem={namespaceColumnIndentRem(depth)}
            sqlTableContext={{
              engine: engineName,
              database: databaseName,
              schema: schema.name,
              namespacePath: namespacePath,
              defaultSchema: defaultSchema,
              defaultDatabase: defaultDatabase,
              dialect: dialect,
            }}
          />
        </>
      )}
    </>
  );
};

const TableList: React.FC<{
  tables: DataTable[];
  sqlTableContext?: SQLTableContext;
  searchValue?: string;
  // Whether `tables` has been enumerated; when false, discovery is deferred and
  // a request is issued on mount (i.e. when the parent is expanded).
  tablesResolved?: boolean;
  // Depth-based indentation (rem) for nested namespace tables/columns. When
  // omitted, the fixed INDENT classes are used (top-level / schemaless tables).
  tableIndentRem?: number;
  columnIndentRem?: number;
}> = ({
  tables,
  sqlTableContext,
  searchValue,
  tablesResolved = true,
  tableIndentRem,
  columnIndentRem,
}) => {
  const { addTableList } = useDataSourceActions();
  const [tablesRequested, setTablesRequested] = React.useState(false);

  // Custom loading state, we need to wait for the data to propagate once requested
  // useAsyncData's loading state may return false before data has propagated
  const [tablesLoading, setTablesLoading] = React.useState(false);

  const { isPending, error } = useAsyncData(async () => {
    if (!tablesResolved && sqlTableContext && !tablesRequested) {
      setTablesRequested(true);
      setTablesLoading(true);

      const { engine, database, schema, namespacePath } = sqlTableContext;
      const previewTableList = await PreviewSQLTableList.request({
        engine: engine,
        database: database,
        schema: schema,
        namespacePath: namespacePath ?? [],
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
  }, [tablesResolved, sqlTableContext, tablesRequested]);

  const stateProps = stateIndentProps(tableIndentRem, INDENT.tableLoading);

  if (isPending || tablesLoading) {
    return <LoadingState message="Loading tables..." {...stateProps} />;
  }

  if (error) {
    return <ErrorState error={error} {...stateProps} />;
  }

  if (tables.length === 0) {
    return <EmptyState content="No tables found" {...stateProps} />;
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
          tableIndentRem={tableIndentRem}
          columnIndentRem={columnIndentRem}
        />
      ))}
    </>
  );
};

const DatasetTableItem: React.FC<{
  table: DataTable;
  sqlTableContext?: SQLTableContext;
  isSearching: boolean;
  tableIndentRem?: number;
  columnIndentRem?: number;
}> = ({
  table,
  sqlTableContext,
  isSearching,
  tableIndentRem,
  columnIndentRem,
}) => {
  const { addTable } = useDataSourceActions();

  const [isExpanded, setIsExpanded] = React.useState(false);
  const [tableDetailsRequested, setTableDetailsRequested] =
    React.useState(false);
  const tableDetailsExist = table.columns.length > 0;

  const { isFetching, isPending, error } = useAsyncData(async () => {
    if (
      isExpanded &&
      !tableDetailsExist &&
      sqlTableContext &&
      !tableDetailsRequested
    ) {
      setTableDetailsRequested(true);
      const { engine, database, schema, namespacePath } = sqlTableContext;
      const previewTable = await PreviewSQLTable.request({
        engine: engine,
        database: database,
        schema: schema,
        tableName: table.name,
        namespacePath: namespacePath ?? [],
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
  const addCodeToNewCell = useAddCodeToNewCell();

  const handleAddTable = () => {
    maybeAddMarimoImport({
      autoInstantiate,
      createNewCell,
      fromCellId: lastFocusedCellId,
    });
    const getCode = () => {
      if (table.source_type === "catalog") {
        // Build the fully-qualified, dotted name including any nested
        // namespace path, e.g. `top.nested.table`.
        const identifier = sqlTableContext?.database
          ? [
              sqlTableContext.database,
              ...(sqlTableContext.namespacePath ?? []),
              table.name,
            ].join(".")
          : table.name;
        return `${table.engine}.load_table("${identifier}")`;
      }

      if (sqlTableContext) {
        return sqlCode({ table, columnName: "*", sqlTableContext });
      }

      switch (table.source_type) {
        case "local":
          return `mo.ui.table(${table.name})`;
        case "duckdb":
        case "connection":
          return sqlCode({ table, columnName: "*", sqlTableContext });
        default:
          logNever(table.source_type);
          return "";
      }
    };

    addCodeToNewCell(getCode());
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
    const stateProps = stateIndentProps(columnIndentRem, INDENT.tableLoading);

    if (isPending || isFetching) {
      return <LoadingState message="Loading columns..." {...stateProps} />;
    }

    if (error) {
      return <ErrorState error={error} {...stateProps} />;
    }

    const columns = table.columns;

    if (columns.length === 0) {
      return <EmptyState content="No columns found" {...stateProps} />;
    }

    return columns.map((column) => (
      <DatasetColumnItem
        key={column.name}
        table={table}
        column={column}
        sqlTableContext={sqlTableContext}
        columnIndentRem={columnIndentRem}
      />
    ));
  };

  const renderTableType = () => {
    if (table.source_type === "local") {
      return;
    }

    const TableTypeIcon = table.type === "table" ? TableIcon : ViewIcon;
    return (
      <TableTypeIcon
        className="h-3 w-3"
        strokeWidth={isExpanded || isSearching ? 2.5 : undefined}
      />
    );
  };

  const uniqueId = sqlTableContext
    ? [
        sqlTableContext.database,
        ...(sqlTableContext.namespacePath ?? []),
        sqlTableContext.schema,
        table.name,
      ].join(".")
    : table.name;

  // Use depth-based indentation for nested namespace tables; otherwise fall
  // back to the fixed schemaless / with-schema classes.
  const useInlineIndent = tableIndentRem != null;

  return (
    <>
      <CommandItem
        className={cn(
          "rounded-none group h-8 cursor-pointer",
          !useInlineIndent &&
            sqlTableContext &&
            (isSchemaless(sqlTableContext.schema)
              ? INDENT.tableSchemaless
              : INDENT.tableWithSchema),
          (isExpanded || isSearching) && "font-semibold",
        )}
        style={
          useInlineIndent ? { paddingLeft: `${tableIndentRem}rem` } : undefined
        }
        value={uniqueId}
        aria-selected={isExpanded}
        forceMount={true}
        onSelect={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex gap-2 items-center flex-1 pl-1">
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
  columnIndentRem?: number;
}> = ({ table, column, sqlTableContext, columnIndentRem }) => {
  const [isExpanded, setIsExpanded] = React.useState(false);
  const closeAllColumns = useAtomValue(closeAllColumnsAtom);
  const setExpandedColumns = useSetAtom(expandedColumnsAtom);

  if (closeAllColumns && isExpanded) {
    setIsExpanded(false);
  }

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

  const addCodeToNewCell = useAddCodeToNewCell();

  const { columnsPreviews } = useDatasets();
  const isPrimaryKey = table.primary_keys?.includes(column.name) || false;
  const isIndexed = table.indexes?.includes(column.name) || false;

  const handleAddColumn = (chartCode: string) => {
    addCodeToNewCell(chartCode);
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

  const columnText = (
    <span className={isExpanded ? "font-semibold" : ""}>{column.name}</span>
  );

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
            columnIndentRem == null &&
              (sqlTableContext ? INDENT.columnSql : INDENT.columnLocal),
          )}
          style={
            columnIndentRem == null
              ? undefined
              : { paddingLeft: `${columnIndentRem}rem` }
          }
        >
          <ColumnName columnName={columnText} dataType={column.type} />
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
        <div
          className={cn(
            INDENT.columnPreview,
            "pr-2 py-2 bg-(--slate-1) shadow-inner border-b",
          )}
        >
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
