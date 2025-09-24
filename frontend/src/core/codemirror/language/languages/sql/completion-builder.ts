/* Copyright 2024 Marimo. All rights reserved. */

import type { Completion } from "@codemirror/autocomplete";
import type { SQLNamespace } from "@codemirror/lang-sql";
import { DefaultSqlTooltipRenders } from "@marimo-team/codemirror-sql";
import type { DataTableColumn } from "@/core/kernel/messages";

/**
 * Simple builder for SQL completion schemas.
 */
export class CompletionBuilder {
  private schema: Record<string, SQLNamespace> = {};

  /**
   * Add a table with its columns at the specified path
   */
  addTable(path: string[], table: string, columns: DataTableColumn[]): this {
    const tableNamespace: SQLNamespace = {
      self: tableToCompletion({
        tableName: table,
        columns: columns,
      }),
      children: columns.map((col) =>
        columnToCompletion({
          tableName: table,
          column: col.name,
          metadata: { Type: col.external_type },
        }),
      ),
    };

    this.setAt([...path, table], tableNamespace);
    return this;
  }

  /**
   * Add a namespace at the specified path
   */
  addNamespace(path: string[], namespace: string): this {
    const namespaceObject: SQLNamespace = {
      self: namespaceToCompletion({
        namespace: namespace,
        path: path,
      }),
      children: {},
    };

    this.setAt(path, namespaceObject);
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

function columnToCompletion(opts: {
  tableName: string;
  column: string;
  metadata?: Record<string, string>;
}): Completion {
  return {
    label: opts.column,
    type: "column",
    info: () => {
      // TODO: do our own styling
      const html = DefaultSqlTooltipRenders.column({
        tableName: opts.tableName,
        columnName: opts.column,
        schema: {},
        metadata: opts.metadata,
      });
      const dom = document.createElement("div");
      dom.innerHTML = html;
      return { dom: dom };
    },
  };
}

function tableToCompletion(opts: {
  tableName: string;
  columns: DataTableColumn[];
  metadata?: Record<string, string>;
}): Completion {
  return {
    label: opts.tableName,
    type: "table",
    info: () => {
      // TODO: do our own styling
      const html = DefaultSqlTooltipRenders.table({
        tableName: opts.tableName,
        columns: opts.columns.map(
          (col) => `${col.name} (${col.external_type})`,
        ),
        metadata: opts.metadata,
      });
      const dom = document.createElement("div");
      dom.innerHTML = html;
      return { dom: dom };
    },
  };
}

function namespaceToCompletion(opts: {
  namespace: string;
  path: string[];
  metadata?: Record<string, string>;
}): Completion {
  return {
    label: opts.namespace,
    detail: opts.path.join("."),
    type: "namespace",
    info: () => {
      // TODO: do our own styling
      const html = DefaultSqlTooltipRenders.namespace({
        path: opts.path,
        type: "namespace",
        semanticType: "namespace",
      });
      const dom = document.createElement("div");
      dom.innerHTML = html;
      return { dom: dom };
    },
  };
}
