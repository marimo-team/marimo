/* Copyright 2024 Marimo. All rights reserved. */

import type { Completion } from "@codemirror/autocomplete";
import { getVariableCompletions } from "@/core/codemirror/completion/variable-completions";
import type { DatasetTablesMap } from "@/core/datasets/data-source-connections";
import type { DataTable } from "@/core/kernel/messages";
import type { Variable, Variables } from "@/core/variables/types";
import type { AIContextItem } from "../registry";
import { AIContextProvider } from "../registry";

const Boosts = {
  LOCAL_TABLE: 5,
  REMOTE_TABLE: 4,
  VARIABLE: 3,
} as const;

// Variable Context Provider
export interface VariableContextItem extends AIContextItem {
  type: "variable";
  data: {
    variable: Variable;
  };
}

export class VariableContextProvider extends AIContextProvider<VariableContextItem> {
  readonly title = "Variables";
  readonly mentionPrefix = "@";
  readonly contextType = "variable";

  constructor(
    private variables: Variables,
    private tablesMap: DatasetTablesMap,
  ) {
    super();
  }

  getItems(): VariableContextItem[] {
    return Object.entries(this.variables).map(([name, variable]) => ({
      id: name,
      label: name,
      type: "variable",
      description: variable.dataType ?? "",
      dataType: variable.dataType,
      data: {
        variable,
      },
    }));
  }

  formatContext(item: VariableContextItem): string {
    const { id, data } = item;
    const { variable } = data;
    return `Variable: ${id}\nType: ${variable.dataType || "unknown"}\nPreview: ${JSON.stringify(variable.value)}`;
  }

  getCompletions(): Completion[] {
    return getVariableCompletions(
      this.variables,
      new Set(this.tablesMap.keys()),
      Boosts.VARIABLE,
      "@",
    );
  }
}

// Table Context Provider
export interface TableContextItem extends AIContextItem {
  type: "table";
  data: DataTable;
}

export class TableContextProvider extends AIContextProvider<TableContextItem> {
  readonly title = "Tables";
  readonly mentionPrefix = "@";
  readonly contextType = "table";

  constructor(private tablesMap: DatasetTablesMap) {
    super();
  }

  getItems(): TableContextItem[] {
    return [...this.tablesMap.entries()].map(([tableName, table]) => ({
      type: "table",
      id: tableName,
      label: tableName,
      description: table.source === "memory" ? "in-memory" : table.source,
      data: table,
    }));
  }

  formatContext(item: TableContextItem): string {
    const { data, id } = item;
    const { columns, source, num_rows, num_columns } = data;
    const shape = [
      num_rows == null ? undefined : `${num_rows} rows`,
      num_columns == null ? undefined : `${num_columns} columns`,
    ]
      .filter(Boolean)
      .join(", ");

    let context = `Table: ${id}\nSource: ${source || "unknown"}`;
    if (shape) {
      context += `\nShape: ${shape}`;
    }

    if (columns && columns.length > 0) {
      context += `\nColumns:\n${columns.map((col) => `  - ${col.name}: ${col.type}`).join("\n")}`;
    }

    return context;
  }

  getCompletions(): Completion[] {
    return [...this.tablesMap.entries()].map(
      ([tableName, table]): Completion => ({
        label: `@${tableName}`,
        displayLabel: tableName,
        detail: table.source === "memory" ? "in-memory" : table.source,
        boost:
          table.source_type === "local"
            ? Boosts.LOCAL_TABLE
            : Boosts.REMOTE_TABLE,
        type: table.variable_name ? "dataframe" : "table",
        apply: `@${tableName}`,
        section: table.variable_name ? "Dataframe" : "Table",
        info: () => this.createTableInfoElement(tableName, table),
      }),
    );
  }

  private createTableInfoElement(
    tableName: string,
    table: DataTable,
  ): HTMLElement {
    const infoContainer = document.createElement("div");
    infoContainer.classList.add(
      "mo-cm-tooltip",
      "docs-documentation",
      "min-w-[200px]",
    );
    infoContainer.style.display = "flex";
    infoContainer.style.flexDirection = "column";
    infoContainer.style.gap = ".8rem";
    infoContainer.style.padding = "0.5rem";

    // Table header with name and source
    const headerDiv = document.createElement("div");
    headerDiv.classList.add("flex", "flex-col", "gap-1");

    const nameDiv = document.createElement("div");
    nameDiv.classList.add("font-bold", "text-base");
    nameDiv.textContent = tableName;
    headerDiv.append(nameDiv);

    if (table.source) {
      const sourceDiv = document.createElement("div");
      sourceDiv.classList.add("text-xs", "text-muted-foreground");
      sourceDiv.textContent = `Source: ${table.source}`;
      headerDiv.append(sourceDiv);
    }

    infoContainer.append(headerDiv);

    // Table shape info
    const shape = [
      table.num_rows == null ? undefined : `${table.num_rows} rows`,
      table.num_columns == null ? undefined : `${table.num_columns} columns`,
    ]
      .filter(Boolean)
      .join(", ");

    if (shape) {
      const shapeDiv = document.createElement("div");
      shapeDiv.classList.add("text-xs", "bg-muted", "px-2", "py-1", "rounded");
      shapeDiv.textContent = shape;
      infoContainer.append(shapeDiv);
    }

    // Columns table (simplified version for brevity)
    if (table.columns && table.columns.length > 0) {
      const columnsDiv = document.createElement("div");
      columnsDiv.classList.add("overflow-auto", "max-h-60");

      const columnsTable = document.createElement("table");
      columnsTable.classList.add("w-full", "text-xs", "border-collapse");

      // Table header
      const headerRow = columnsTable.insertRow();
      headerRow.classList.add("bg-muted");

      const nameHeader = headerRow.insertCell();
      nameHeader.classList.add("p-2", "font-medium", "text-left");
      nameHeader.textContent = "Column";

      const typeHeader = headerRow.insertCell();
      typeHeader.classList.add("p-2", "font-medium", "text-left");
      typeHeader.textContent = "Type";

      // Table rows
      table.columns.forEach((column, index) => {
        const row = columnsTable.insertRow();
        row.classList.add(index % 2 === 0 ? "bg-background" : "bg-muted/30");

        const nameCell = row.insertCell();
        nameCell.classList.add("p-2", "font-mono");
        nameCell.textContent = column.name;

        const typeCell = row.insertCell();
        typeCell.classList.add("p-2", "text-muted-foreground");
        typeCell.textContent = column.type;
      });

      columnsDiv.append(columnsTable);
      infoContainer.append(columnsDiv);
    }

    return infoContainer;
  }
}
