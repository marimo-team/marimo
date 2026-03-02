/* Copyright 2026 Marimo. All rights reserved. */

import { useState } from "react";
import type { z } from "zod";
import { DatabaseLogo, type DBLogoName } from "@/components/databases/icon";
import { ConnectionForm, SelectorButton, SelectorGrid } from "../components";
import {
  ConnectionDisplayNames,
  type ConnectionLibrary,
  generateDatabaseCode,
} from "./as-code";
import {
  BigQueryConnectionSchema,
  ChdbConnectionSchema,
  ClickhouseConnectionSchema,
  type DatabaseConnection,
  DatabricksConnectionSchema,
  DataFusionConnectionSchema,
  DuckDBConnectionSchema,
  IcebergConnectionSchema,
  MotherDuckConnectionSchema,
  MySQLConnectionSchema,
  PostgresConnectionSchema,
  PySparkConnectionSchema,
  RedshiftConnectionSchema,
  SnowflakeConnectionSchema,
  SQLiteConnectionSchema,
  SupabaseConnectionSchema,
  TimeplusConnectionSchema,
  TrinoConnectionSchema,
} from "./schemas";

interface ConnectionSchema {
  name: string;
  schema: z.ZodType<DatabaseConnection>;
  color: string;
  logo: DBLogoName;
  connectionLibraries: {
    libraries: ConnectionLibrary[];
    preferred: ConnectionLibrary;
  };
}

const DATABASES = [
  {
    name: "PostgreSQL",
    schema: PostgresConnectionSchema,
    color: "#336791",
    logo: "postgres",
    connectionLibraries: {
      libraries: ["sqlalchemy", "sqlmodel"],
      preferred: "sqlalchemy",
    },
  },
  {
    name: "MySQL",
    schema: MySQLConnectionSchema,
    color: "#00758F",
    logo: "mysql",
    connectionLibraries: {
      libraries: ["sqlalchemy", "sqlmodel"],
      preferred: "sqlalchemy",
    },
  },
  {
    name: "SQLite",
    schema: SQLiteConnectionSchema,
    color: "#003B57",
    logo: "sqlite",
    connectionLibraries: {
      libraries: ["sqlalchemy", "sqlmodel"],
      preferred: "sqlalchemy",
    },
  },
  {
    name: "DuckDB",
    schema: DuckDBConnectionSchema,
    color: "#FFD700",
    logo: "duckdb",
    connectionLibraries: {
      libraries: ["duckdb"],
      preferred: "duckdb",
    },
  },
  {
    name: "MotherDuck",
    schema: MotherDuckConnectionSchema,
    color: "#ff9538",
    logo: "motherduck",
    connectionLibraries: {
      libraries: ["duckdb"],
      preferred: "duckdb",
    },
  },
  {
    name: "Snowflake",
    schema: SnowflakeConnectionSchema,
    color: "#29B5E8",
    logo: "snowflake",
    connectionLibraries: {
      libraries: ["sqlalchemy", "sqlmodel"],
      preferred: "sqlalchemy",
    },
  },
  {
    name: "ClickHouse",
    schema: ClickhouseConnectionSchema,
    color: "#2C2C1D",
    logo: "clickhouse",
    connectionLibraries: {
      libraries: ["clickhouse_connect"],
      preferred: "clickhouse_connect",
    },
  },
  {
    name: "Timeplus",
    schema: TimeplusConnectionSchema,
    color: "#B83280",
    logo: "timeplus",
    connectionLibraries: {
      libraries: ["sqlalchemy", "sqlmodel"],
      preferred: "sqlalchemy",
    },
  },
  {
    name: "BigQuery",
    schema: BigQueryConnectionSchema,
    color: "#4285F4",
    logo: "bigquery",
    connectionLibraries: {
      libraries: ["sqlalchemy", "sqlmodel"],
      preferred: "sqlalchemy",
    },
  },
  {
    name: "ClickHouse Embedded",
    schema: ChdbConnectionSchema,
    color: "#f2b611",
    logo: "clickhouse",
    connectionLibraries: {
      libraries: ["chdb"],
      preferred: "chdb",
    },
  },
  {
    name: "Trino",
    schema: TrinoConnectionSchema,
    color: "#d466b6",
    logo: "trino",
    connectionLibraries: {
      libraries: ["sqlalchemy", "sqlmodel"],
      preferred: "sqlalchemy",
    },
  },
  {
    name: "DataFusion",
    schema: DataFusionConnectionSchema,
    color: "#202A37",
    logo: "datafusion",
    connectionLibraries: {
      libraries: ["ibis"],
      preferred: "ibis",
    },
  },
  {
    name: "PySpark",
    schema: PySparkConnectionSchema,
    color: "#1C5162",
    logo: "pyspark",
    connectionLibraries: {
      libraries: ["ibis"],
      preferred: "ibis",
    },
  },
  {
    name: "Redshift",
    schema: RedshiftConnectionSchema,
    color: "#522BAE",
    logo: "redshift",
    connectionLibraries: {
      libraries: ["redshift"],
      preferred: "redshift",
    },
  },
  {
    name: "Databricks",
    schema: DatabricksConnectionSchema,
    color: "#c41e0c",
    logo: "databricks",
    connectionLibraries: {
      libraries: ["sqlalchemy", "sqlmodel", "ibis"],
      preferred: "sqlalchemy",
    },
  },
  {
    name: "Supabase",
    schema: SupabaseConnectionSchema,
    color: "#238F5F",
    logo: "supabase",
    connectionLibraries: {
      libraries: ["sqlalchemy", "sqlmodel"],
      preferred: "sqlalchemy",
    },
  },
] satisfies ConnectionSchema[];

const DATA_CATALOGS = [
  {
    name: "Iceberg",
    schema: IcebergConnectionSchema,
    color: "#000000",
    logo: "iceberg",
    connectionLibraries: {
      libraries: ["pyiceberg"],
      preferred: "pyiceberg",
    },
  },
] satisfies ConnectionSchema[];

const ALL_ENTRIES = [...DATABASES, ...DATA_CATALOGS];

const DatabaseSchemaSelector: React.FC<{
  onSelect: (schema: z.ZodType<DatabaseConnection>) => void;
}> = ({ onSelect }) => {
  return (
    <>
      <SelectorGrid>
        {DATABASES.map(({ name, schema, color, logo }) => (
          <SelectorButton
            key={name}
            name={name}
            color={color}
            icon={
              <DatabaseLogo
                name={logo}
                className="w-8 h-8 text-white brightness-0 invert dark:invert"
              />
            }
            onSelect={() => onSelect(schema)}
          />
        ))}
      </SelectorGrid>
      <h4 className="font-semibold text-muted-foreground text-lg flex items-center gap-4 my-2">
        Data Catalogs
        <hr className="flex-1" />
      </h4>
      <SelectorGrid>
        {DATA_CATALOGS.map(({ name, schema, color, logo }) => (
          <SelectorButton
            key={name}
            name={name}
            color={color}
            icon={
              <DatabaseLogo
                name={logo}
                className="w-8 h-8 text-white brightness-0 invert dark:invert"
              />
            }
            onSelect={() => onSelect(schema)}
          />
        ))}
      </SelectorGrid>
    </>
  );
};

export const AddDatabaseForm: React.FC<{
  onSubmit: () => void;
  header?: React.ReactNode;
}> = ({ onSubmit, header }) => {
  const [selectedSchema, setSelectedSchema] =
    useState<z.ZodType<DatabaseConnection> | null>(null);

  if (!selectedSchema) {
    return (
      <>
        {header}
        <div>
          <DatabaseSchemaSelector onSelect={setSelectedSchema} />
        </div>
      </>
    );
  }

  const entry = ALL_ENTRIES.find((e) => e.schema === selectedSchema);
  const libs = entry?.connectionLibraries;

  return (
    <ConnectionForm<DatabaseConnection>
      schema={selectedSchema}
      libraries={libs?.libraries ?? []}
      preferredLibrary={libs?.preferred ?? "sqlalchemy"}
      displayNames={ConnectionDisplayNames}
      libraryLabel="Preferred connection library"
      generateCode={(values, library) =>
        generateDatabaseCode(values, library as ConnectionLibrary)
      }
      onSubmit={onSubmit}
      onBack={() => setSelectedSchema(null)}
    />
  );
};
