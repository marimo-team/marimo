/* Copyright 2026 Marimo. All rights reserved. */

import type {
  Database,
  DatabaseSchema,
  DataTable,
} from "@/core/kernel/messages";

export function makeTable(
  name: string,
  overrides: Partial<DataTable> = {},
): DataTable {
  return {
    kind: "data_table",
    name,
    columns: [],
    num_columns: 0,
    num_rows: 0,
    variable_name: null,
    source: "",
    source_type: "local",
    type: "table",
    ...overrides,
  };
}

export function makeSchema(
  name: string,
  tables: DataTable[] = [],
): DatabaseSchema {
  return { kind: "schema", name, tables };
}

interface SchemaFixture {
  name: string;
  tables: DataTable[];
}

/** Build a `Database` from simple schema/table fixtures used in tests. */
export function databaseWithSchemas({
  name,
  dialect,
  schemas,
  overrides = {},
}: {
  name: string;
  dialect: string;
  schemas: SchemaFixture[];
  overrides?: Partial<Omit<Database, "name" | "dialect" | "children">>;
}): Database {
  return {
    name,
    dialect,
    children: schemas.map((schema) => makeSchema(schema.name, schema.tables)),
    ...overrides,
  };
}
