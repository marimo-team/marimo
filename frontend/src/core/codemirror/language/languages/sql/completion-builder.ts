/* Copyright 2026 Marimo. All rights reserved. */

import type { Completion } from "@codemirror/autocomplete";
import type { SQLNamespace } from "@codemirror/lang-sql";
import { createRoot } from "react-dom/client";
import type {
  Database,
  DatabaseSchema,
  DataTable,
  DataTableColumn,
} from "@/core/kernel/messages";
import {
  renderColumnInfo,
  renderDatabaseInfo,
  renderSchemaInfo,
  renderTableInfo,
} from "./renderers";

/**
 * Simple builder for SQL completion schemas.
 */
export class CompletionBuilder {
  private schema: Record<string, SQLNamespace> = {};

  /**
   * Add a table with its columns at the specified path
   */
  addTable(path: string[], table: DataTable): this {
    const tableNamespace: SQLNamespace = {
      self: tableToCompletion({
        table: table,
      }),
      children: table.columns.map((col) =>
        columnToCompletion({
          column: col,
        }),
      ),
    };

    this.setAt([...path, table.name], tableNamespace);
    return this;
  }

  /**
   * Add a schema at the specified path
   */
  addSchema(path: string[], schema: DatabaseSchema): this {
    const schemaObject: SQLNamespace = {
      self: schemaToCompletion({
        namespace: schema,
        path: path,
      }),
      children: {},
    };

    this.setAt(path, schemaObject);
    return this;
  }

  /**
   * Add a database at the specified path
   */
  addDatabase(path: string[], database: Database): this {
    const databaseObject: SQLNamespace = {
      self: databaseToCompletion({
        namespace: database,
        path: path,
      }),
      children: {},
    };
    this.setAt(path, databaseObject);
    return this;
  }

  /**
   * Set a value at a nested path, creating intermediate objects as needed
   */
  private setAt(path: string[], value: SQLNamespace): void {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let current: any = this.schema;
    for (const key of path.slice(0, -1)) {
      if (!current[key]) {
        current[key] = { children: {} };
      }
      current = current[key].children;
    }
    current[path[path.length - 1]] = value;
  }

  /**
   * Build the final schema
   */
  build(): SQLNamespace {
    return this.schema;
  }

  /**
   * Reset for reuse
   */
  reset(): this {
    this.schema = {};
    return this;
  }
}

function columnToCompletion(opts: { column: DataTableColumn }): Completion {
  return {
    label: opts.column.name,
    type: "column",
    info: () => {
      const dom = document.createElement("div");
      createRoot(dom).render(renderColumnInfo(opts.column));
      return { dom: dom };
    },
  };
}

function tableToCompletion(opts: { table: DataTable }): Completion {
  return {
    label: opts.table.name,
    type: "table",
    info: () => {
      const dom = document.createElement("div");
      createRoot(dom).render(renderTableInfo(opts.table));
      return { dom: dom };
    },
  };
}

function schemaToCompletion(opts: {
  namespace: DatabaseSchema;
  path: string[];
}): Completion {
  return {
    label: opts.namespace.name,
    detail: opts.path.join("."),
    type: "schema",
    info: () => {
      const dom = document.createElement("div");
      createRoot(dom).render(renderSchemaInfo(opts.namespace));
      return { dom: dom };
    },
  };
}

function databaseToCompletion(opts: {
  namespace: Database;
  path: string[];
}): Completion {
  return {
    label: opts.namespace.name,
    detail: opts.path.join("."),
    type: "database",
    info: () => {
      const dom = document.createElement("div");
      createRoot(dom).render(renderDatabaseInfo(opts.namespace));
      return { dom: dom };
    },
  };
}
