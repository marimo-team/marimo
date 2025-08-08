/* Copyright 2024 Marimo. All rights reserved. */

import type { Completion } from "@codemirror/autocomplete";
import type { DatasetTablesMap } from "@/core/datasets/data-source-connections";
import type { DataTable } from "@/core/kernel/messages";
import type { AIContextItem } from "../registry";
import { AIContextProvider } from "../registry";
import { Boosts } from "./common";

export interface TableContextItem extends AIContextItem {
  type: "table";
  data: DataTable;
}

export class TableContextProvider extends AIContextProvider<TableContextItem> {
  readonly title = "Tables";
  readonly mentionPrefix = "@";
  readonly contextType = "data";

  constructor(private tablesMap: DatasetTablesMap) {
    super();
  }

  getItems(): TableContextItem[] {
    return [...this.tablesMap.entries()].map(([tableName, table]) => ({
      uri: this.asURI(tableName),
      name: tableName,
      type: "table",
      description: table.source === "memory" ? "in-memory" : table.source,
      data: table,
    }));
  }

  formatContext(item: TableContextItem): string {
    const { data, uri: id } = item;
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
    return [];
  }

  formatCompletion(item: TableContextItem): Completion {
    const tableName = item.data.name;
    const table = item.data;
    return {
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
    };
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

    // Columns table
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

      // Check if any column has metadata before adding the header
      const hasAnyMetadata = table.columns.some(
        (column) => this.getItemMetadata(table, column) !== undefined,
      );

      let metadataHeader: HTMLTableCellElement | undefined;
      if (hasAnyMetadata) {
        metadataHeader = headerRow.insertCell();
        metadataHeader.classList.add("p-2", "font-medium", "text-left");
        metadataHeader.textContent = "Metadata";
      }

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

        if (hasAnyMetadata) {
          const metadataCell = row.insertCell();
          metadataCell.classList.add("p-2");

          const itemMetadata = this.getItemMetadata(table, column);
          if (itemMetadata) {
            metadataCell.append(itemMetadata);
          }
        }
      });

      columnsDiv.append(columnsTable);
      infoContainer.append(columnsDiv);
    }

    return infoContainer;
  }

  private getItemMetadata(
    table: DataTable,
    column: DataTable["columns"][0],
  ): HTMLSpanElement | undefined {
    const isPrimaryKey = table.primary_keys?.includes(column.name);
    const isIndexed = table.indexes?.includes(column.name);
    if (isPrimaryKey || isIndexed) {
      const badge = document.createElement("span");
      badge.textContent = isPrimaryKey ? "PK" : "IDX";
      const color = isPrimaryKey
        ? "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200"
        : "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200";
      badge.classList.add(
        "text-xs",
        "px-1.5",
        "py-0.5",
        "rounded-full",
        "font-medium",
        ...color.split(" "),
      );
      return badge;
    }
  }
}
