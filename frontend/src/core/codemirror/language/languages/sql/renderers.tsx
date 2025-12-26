/* Copyright 2026 Marimo. All rights reserved. */

import { HashIcon, InfoIcon } from "lucide-react";
import type React from "react";
import { dbDisplayName } from "@/components/databases/display";
import {
  ColumnIcon,
  DatabaseIcon,
  DatasourceIcon,
  IndexIcon,
  PrimaryKeyIcon,
  SchemaIcon,
  TableIcon,
  ViewIcon,
} from "@/components/databases/namespace-icons";
import { DATA_TYPE_ICON } from "@/components/datasets/icons";
import { Badge } from "@/components/ui/badge";
import {
  type ConnectionName,
  INTERNAL_SQL_ENGINES,
} from "@/core/datasets/engines";
import type {
  Database,
  DatabaseSchema,
  DataSourceConnection,
  DataTable,
  DataTableColumn,
  DataType,
} from "@/core/kernel/messages";
import { PluralWord } from "@/utils/pluralize";

// Configuration constants
const PREVIEW_ITEM_LIMIT = 5;

// Color mappings for data types (Tailwind-safe)
const DATA_TYPE_COLORS: Record<DataType, string> = {
  boolean: "bg-[var(--orange-4)] text-[var(--orange-11)]",
  date: "bg-[var(--grass-4)] text-[var(--grass-11)]",
  time: "bg-[var(--grass-4)] text-[var(--grass-11)]",
  datetime: "bg-[var(--grass-4)] text-[var(--grass-11)]",
  number: "bg-[var(--purple-4)] text-[var(--purple-11)]",
  integer: "bg-[var(--purple-4)] text-[var(--purple-11)]",
  string: "bg-[var(--blue-4)] text-[var(--blue-11)]",
  unknown: "bg-[var(--slate-4)] text-[var(--slate-11)]",
};

// Source type colors
const SOURCE_TYPE_COLORS = {
  local: "bg-[var(--blue-4)] text-[var(--blue-11)]",
  duckdb: "bg-[var(--amber-4)] text-[var(--amber-11)]",
  connection: "bg-[var(--green-4)] text-[var(--green-11)]",
  catalog: "bg-[var(--purple-4)] text-[var(--purple-11)]",
} as const;

const CONTAINER_STYLES = "p-3 min-w-[250px] flex flex-col divide-y";

const columnsText = new PluralWord("column", "columns");
const rowsText = new PluralWord("row", "rows");
const schemasText = new PluralWord("schema", "schemas");
const tablesText = new PluralWord("table", "tables");
const databasesText = new PluralWord("database", "databases");

// Helper components and functions
const SectionHeader: React.FC<{
  icon: React.ReactNode;
  title: string;
  badge?: React.ReactNode;
}> = ({ icon, title, badge }) => (
  <div className="flex items-center gap-2 pb-2">
    {icon}
    <h3 className="font-semibold text-sm">{title}</h3>
    {badge}
  </div>
);

const MetadataRow: React.FC<{
  label: string;
  value: React.ReactNode;
}> = ({ label, value }) => (
  <div className="flex items-center justify-between text-xs">
    <span className="text-[var(--slate-11)]">{label}:</span>
    {value}
  </div>
);

const StatisticItem: React.FC<{
  icon: React.ReactNode;
  text: string;
}> = ({ icon, text }) => (
  <div className="flex items-center gap-1">
    {icon}
    <span className="text-xs text-[var(--slate-11)]">{text}</span>
  </div>
);

const PreviewList: React.FC<{
  title?: string;
  items: React.ReactNode[];
  totalCount: number;
  limit?: number;
}> = ({ title = "", items, totalCount, limit = PREVIEW_ITEM_LIMIT }) => {
  if (items.length === 0) {
    return null;
  }

  const visibleItems = items.slice(0, limit);
  const hasMore = totalCount > limit;

  return (
    <div className="py-2">
      {title && (
        <h4 className="text-xs font-medium text-[var(--slate-11)] mb-2">
          {title}:
        </h4>
      )}
      <div className="flex flex-col gap-1 overflow-y-auto">
        {visibleItems}
        {hasMore && (
          <div className="text-xs text-[var(--slate-10)] text-center py-1">
            ... and {totalCount - limit} more
          </div>
        )}
      </div>
    </div>
  );
};

const getDataTypeColorClass = (dataType: DataType): string => {
  return DATA_TYPE_COLORS[dataType] || DATA_TYPE_COLORS.unknown;
};

export const renderTableInfo = (table: DataTable): React.ReactNode => {
  const tableIcon =
    table.type === "view" ? (
      <ViewIcon className="w-4 h-4 text-[var(--blue-9)]" />
    ) : (
      <TableIcon className="w-4 h-4 text-[var(--green-9)]" />
    );

  const typeBadge = (
    <Badge
      variant="secondary"
      className={`text-xs ${
        table.type === "view"
          ? "bg-[var(--blue-4)] text-[var(--blue-11)]"
          : "bg-[var(--green-4)] text-[var(--green-11)]"
      }`}
    >
      {table.type}
    </Badge>
  );

  const columnItems = table.columns.map((column) => {
    const TypeIcon = DATA_TYPE_ICON[column.type];
    return (
      <div
        key={column.name}
        className="flex items-center justify-between text-xs rounded"
      >
        <div className="flex items-center gap-2">
          <TypeIcon className="w-3 h-3 text-[var(--slate-9)]" />
          <span className="font-mono">{column.name}</span>
        </div>
        <Badge
          variant="outline"
          className={`text-xs ${getDataTypeColorClass(column.type)}`}
        >
          {column.type}
        </Badge>
      </div>
    );
  });

  const hasPrimaryKeys = table.primary_keys && table.primary_keys.length > 0;
  const hasIndexes = table.indexes && table.indexes.length > 0;

  return (
    <div className={`${CONTAINER_STYLES} min-w-[300px]`}>
      <SectionHeader icon={tableIcon} title={table.name} badge={typeBadge} />

      {/* Metadata */}
      <div className="flex flex-col gap-2 py-2">
        <MetadataRow
          label="Source"
          value={
            <Badge
              variant="outline"
              className={`text-xs ${SOURCE_TYPE_COLORS[table.source_type]}`}
            >
              {table.source}
            </Badge>
          }
        />

        {table.variable_name && (
          <MetadataRow
            label="Variable"
            value={
              <code className="text-xs bg-[var(--slate-4)] px-1 rounded">
                {table.variable_name}
              </code>
            }
          />
        )}

        {table.engine && (
          <MetadataRow
            label="Engine"
            value={
              <code className="text-xs bg-[var(--slate-4)] px-1 rounded">
                {table.engine}
              </code>
            }
          />
        )}
      </div>

      {/* Statistics */}
      {(table.num_columns != null || table.num_rows != null) && (
        <div className="grid grid-cols-2 gap-2 py-2">
          {table.num_columns != null && (
            <StatisticItem
              icon={<ColumnIcon className="w-3 h-3 text-[var(--slate-9)]" />}
              text={`${table.num_columns} ${columnsText.pluralize(table.num_columns)}`}
            />
          )}
          {table.num_rows != null && (
            <StatisticItem
              icon={<HashIcon className="w-3 h-3 text-[var(--slate-9)]" />}
              text={`${table.num_rows} ${rowsText.pluralize(table.num_rows)}`}
            />
          )}
        </div>
      )}

      {/* Empty Info */}
      {table.columns.length === 0 && renderEmptyInfo("column")}

      {/* Primary Keys & Indexes */}
      {(hasPrimaryKeys || hasIndexes) && (
        <div className="flex flex-col gap-2 py-2">
          {hasPrimaryKeys && (
            <div className="flex flex-row gap-1">
              <div className="flex items-center gap-1">
                <PrimaryKeyIcon className="w-3 h-3 text-[var(--amber-9)]" />
                <span className="text-xs font-medium text-[var(--slate-11)]">
                  Primary Keys:
                </span>
              </div>
              {table.primary_keys?.map((key) => (
                <Badge
                  key={key}
                  variant="outline"
                  className="text-xs text-[var(--slate-11)]"
                >
                  {key}
                </Badge>
              ))}
            </div>
          )}

          {hasIndexes && (
            <div className="flex flex-row gap-1">
              <div className="flex items-center gap-1 mb-1">
                <IndexIcon className="w-3 h-3 text-[var(--purple-9)]" />
                <span className="text-xs font-medium text-[var(--slate-11)]">
                  Indexes:
                </span>
              </div>
              {table.indexes?.map((index) => (
                <Badge
                  key={index}
                  variant="outline"
                  className="text-xs text-[var(--slate-11)]"
                >
                  {index}
                </Badge>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Sample Columns Preview */}
      {table.columns.length > 0 && (
        <PreviewList items={columnItems} totalCount={table.columns.length} />
      )}
    </div>
  );
};

export const renderColumnInfo = (column: DataTableColumn): React.ReactNode => {
  const TypeIcon = DATA_TYPE_ICON[column.type];

  const typeBadge = (
    <Badge
      variant="outline"
      className={`text-xs ${getDataTypeColorClass(column.type)}`}
    >
      {column.type}
    </Badge>
  );

  const sampleItems =
    column.sample_values?.map((value, index) => (
      <div
        key={index}
        className="text-xs bg-[var(--slate-3)] rounded font-mono"
      >
        {value === null || value === undefined ? "null" : String(value)}
      </div>
    )) || [];

  return (
    <div className={CONTAINER_STYLES}>
      <SectionHeader
        icon={<TypeIcon className="w-4 h-4 text-[var(--slate-9)]" />}
        title={column.name}
        badge={typeBadge}
      />

      {/* Type Information */}
      <div className="flex flex-col gap-2 mt-2">
        <MetadataRow
          label="Type"
          value={<span className="font-medium">{column.type}</span>}
        />
        <MetadataRow
          label="External Type"
          value={
            <code className="text-xs bg-[var(--slate-4)] px-1 rounded">
              {column.external_type}
            </code>
          }
        />
      </div>

      {/* Sample Values */}
      {column.sample_values && column.sample_values.length > 0 && (
        <PreviewList
          title="Sample Values"
          items={sampleItems}
          totalCount={column.sample_values.length}
        />
      )}
    </div>
  );
};

export const renderDatabaseInfo = (database: Database): React.ReactNode => {
  const dialectBadge = (
    <Badge
      variant="outline"
      className="text-xs bg-[var(--blue-4)] text-[var(--blue-11)]"
    >
      {database.dialect}
    </Badge>
  );

  const schemaItems = database.schemas.map((schema) => (
    <div
      key={schema.name}
      className="flex items-center justify-between text-xs rounded hover:bg-[var(--slate-3)]"
    >
      <div className="flex items-center gap-2">
        <SchemaIcon className="w-3 h-3 text-[var(--slate-9)]" />
        <span>{schema.name}</span>
      </div>
      <Badge variant="outline" className="text-xs">
        {schema.tables.length} {tablesText.pluralize(schema.tables.length)}
      </Badge>
    </div>
  ));

  return (
    <div className={CONTAINER_STYLES}>
      <SectionHeader
        icon={<DatabaseIcon className="w-4 h-4 text-[var(--blue-9)]" />}
        title={database.name}
        badge={dialectBadge}
      />
      {/* Metadata */}
      <div className="flex flex-col gap-2 py-2">
        <MetadataRow
          label="Dialect"
          value={<span className="font-medium">{database.dialect}</span>}
        />

        {database.engine && (
          <MetadataRow
            label="Engine"
            value={
              <code className="text-xs bg-[var(--slate-4)] px-1 rounded">
                {database.engine}
              </code>
            }
          />
        )}
      </div>
      {/* Schema Statistics */}
      <div className="py-2">
        <StatisticItem
          icon={<SchemaIcon className="w-3 h-3 text-[var(--slate-9)]" />}
          text={`${database.schemas.length} schema${database.schemas.length === 1 ? "" : "s"}`}
        />
      </div>
      {/* Empty Info */}
      {database.schemas.length === 0 && renderEmptyInfo("schema")}

      {/* Schema Preview */}
      {database.schemas.length > 0 && (
        <PreviewList
          title="Schemas"
          items={schemaItems}
          totalCount={database.schemas.length}
        />
      )}
    </div>
  );
};

export const renderSchemaInfo = (schema: DatabaseSchema): React.ReactNode => {
  const schemaBadge = (
    <Badge
      variant="outline"
      className="text-xs bg-[var(--green-4)] text-[var(--green-11)]"
    >
      Schema
    </Badge>
  );

  const tableItems = schema.tables.map((table) => (
    <div
      key={table.name}
      className="flex items-center justify-between text-xs rounded hover:bg-[var(--slate-3)]"
    >
      <div className="flex items-center gap-2">
        {table.type === "view" ? (
          <ViewIcon className="w-3 h-3 text-[var(--blue-9)]" />
        ) : (
          <TableIcon className="w-3 h-3 text-[var(--green-9)]" />
        )}
        <span>{table.name}</span>
      </div>
      <Badge
        variant="outline"
        className={`text-xs ${
          table.type === "view"
            ? "bg-[var(--blue-4)] text-[var(--blue-11)]"
            : "bg-[var(--green-4)] text-[var(--green-11)]"
        }`}
      >
        {table.type}
      </Badge>
    </div>
  ));

  return (
    <div className={CONTAINER_STYLES}>
      <SectionHeader
        icon={<SchemaIcon className="w-4 h-4 text-[var(--green-9)]" />}
        title={schema.name}
        badge={schemaBadge}
      />

      {/* Table Statistics */}
      <div className="py-2">
        <StatisticItem
          icon={<TableIcon className="w-3 h-3 text-[var(--slate-9)]" />}
          text={`${schema.tables.length} table${schema.tables.length === 1 ? "" : "s"}`}
        />
      </div>

      {/* Empty Info */}
      {schema.tables.length === 0 && renderEmptyInfo("table")}

      {/* Table Preview */}
      {schema.tables.length > 0 && (
        <PreviewList
          title="Tables"
          items={tableItems}
          totalCount={schema.tables.length}
        />
      )}
    </div>
  );
};

const DefaultBadge = <Badge variant="outline">default</Badge>;
const MAX_SCHEMAS_TO_DISPLAY = 8;
const MAX_TABLES_TO_DISPLAY = 3;

export const renderDatasourceInfo = (
  connection: DataSourceConnection,
  dataframes?: DataTable[],
): React.ReactNode => {
  const databaseCount = connection.databases.length;
  const schemasCount = connection.databases.reduce(
    (count, db) => count + db.schemas.length,
    0,
  );

  const renderSchema = (schema: DatabaseSchema, isDefaultDb: boolean) => {
    if (schema.tables.length === 0) {
      return null;
    }

    const isDefaultSchema =
      schema.name === connection.default_schema && isDefaultDb;

    let tableItems: React.ReactNode[] = [];
    // Don't display table items if there are many schemas
    if (schemasCount < MAX_SCHEMAS_TO_DISPLAY) {
      tableItems = schema.tables
        .slice(0, MAX_TABLES_TO_DISPLAY + 1)
        .map((table) => {
          return (
            <div key={table.name} className="flex items-center gap-2 ml-4">
              <TableIcon className="w-3 h-3 text-[var(--green-9)]" />
              <span className="text-xs">{table.name}</span>
            </div>
          );
        });
    }

    return (
      <div key={schema.name}>
        <div className="flex items-center gap-2 text-xs rounded hover:bg-[var(--slate-3)] ml-2">
          <SchemaIcon className="w-3 h-3 text-[var(--slate-9)]" />
          <span>{schema.name}</span>
          {isDefaultSchema && DefaultBadge}
          <Badge variant="outline" className="text-xs ml-auto">
            {schema.tables.length} tables
          </Badge>
        </div>
        <PreviewList
          items={tableItems}
          totalCount={schema.tables.length}
          limit={MAX_TABLES_TO_DISPLAY}
        />
      </div>
    );
  };

  const databaseItems = connection.databases.map((db) => {
    const isDefaultDb =
      db.name === connection.default_database ||
      connection.databases.length === 1;

    const schemaItems = db.schemas.map((schema) =>
      renderSchema(schema, isDefaultDb),
    );

    return (
      <div key={db.name}>
        <div className="flex items-center gap-2">
          <DatabaseIcon className="w-3 h-3 text-[var(--blue-9)]" />
          <span className="text-xs">{db.name}</span>
          {isDefaultDb && DefaultBadge}
        </div>
        {schemaItems && (
          <PreviewList items={schemaItems} totalCount={db.schemas.length} />
        )}
      </div>
    );
  });

  let title = connection.name;
  if (INTERNAL_SQL_ENGINES.has(connection.name as ConnectionName)) {
    title = "In-Memory";
  }

  const dataframeItems = dataframes?.map((table) => (
    <div key={table.name} className="flex items-center gap-2">
      <TableIcon className="w-3 h-3 text-[var(--blue-9)]" />
      <span className="text-xs">{table.name}</span>
    </div>
  ));

  return (
    <div className={`${CONTAINER_STYLES} px-1`}>
      <SectionHeader
        icon={<DatasourceIcon className="w-4 h-4 text-[var(--purple-9)]" />}
        title={title}
      />

      {/* Metadata */}
      <div className="flex flex-col gap-2 py-2">
        <MetadataRow
          label="Dialect"
          value={
            <span className="font-medium">
              {dbDisplayName(connection.dialect)}
            </span>
          }
        />
        <MetadataRow
          label="Source"
          value={
            <Badge
              variant="outline"
              className="text-xs bg-[var(--green-4)] text-[var(--green-11)]"
            >
              {connection.source}
            </Badge>
          }
        />
      </div>

      {/* Statistics */}
      <div className="flex flex-row justify-between py-2">
        <StatisticItem
          icon={<DatabaseIcon className="w-3 h-3 text-[var(--slate-9)]" />}
          text={`${databaseCount} ${databasesText.pluralize(databaseCount)}`}
        />
        <StatisticItem
          icon={<SchemaIcon className="w-3 h-3 text-[var(--slate-9)]" />}
          text={`${schemasCount} ${schemasText.pluralize(schemasCount)}`}
        />
      </div>

      {/* Database Preview */}
      {databaseCount > 0 && (
        <PreviewList items={databaseItems} totalCount={databaseCount} />
      )}

      {/* Tables Preview */}
      {dataframeItems && dataframeItems.length > 0 && (
        <PreviewList
          title="Dataframes"
          items={dataframeItems}
          totalCount={dataframeItems.length}
        />
      )}
    </div>
  );
};

export const renderEmptyInfo = (
  type: "column" | "table" | "schema" | "database",
) => {
  return (
    <div className="flex items-start gap-2 mt-3">
      <InfoIcon size={10} className="mt-1 text-[var(--slate-10)] shrink-0" />
      <span className="text-xs text-[var(--slate-11)]">
        No {type} information available.{" \n"}
        <span className="text-[var(--blue-10)]">
          Introspect to see more details.
        </span>
      </span>
    </div>
  );
};
