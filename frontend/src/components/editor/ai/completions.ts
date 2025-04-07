/* Copyright 2024 Marimo. All rights reserved. */

import type { DatasetTablesMap } from "@/core/datasets/data-source-connections";
import type { DataTable } from "@/core/kernel/messages";
import type { Completion } from "@codemirror/autocomplete";
import type { Variable, Variables } from "@/core/variables/types";

const Boosts = {
  LOCAL_TABLE: 5,
  REMOTE_TABLE: 4,
  VARIABLE: 3,
} as const;

export function getTableCompletions(tablesMap: DatasetTablesMap) {
  return [...tablesMap.entries()].map(
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
      // This may break in future, but if if it has a variable name,
      // then it is a dataframe, otherwise it is a table.
      section: table.variable_name ? "Dataframe" : "Table",
      info: () => {
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
          table.num_columns == null
            ? undefined
            : `${table.num_columns} columns`,
        ]
          .filter(Boolean)
          .join(", ");

        if (shape) {
          const shapeDiv = document.createElement("div");
          shapeDiv.classList.add(
            "text-xs",
            "bg-muted",
            "px-2",
            "py-1",
            "rounded",
          );
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
            (column) => getItemMetadata(table, column) !== undefined,
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
            row.classList.add(
              index % 2 === 0 ? "bg-background" : "bg-muted/30",
            );

            const nameCell = row.insertCell();
            nameCell.classList.add("p-2", "font-mono");
            nameCell.textContent = column.name;

            const typeCell = row.insertCell();
            typeCell.classList.add("p-2", "text-muted-foreground");
            typeCell.textContent = column.type;

            if (hasAnyMetadata) {
              const metadataCell = row.insertCell();
              metadataCell.classList.add("p-2");

              const itemMetadata = getItemMetadata(table, column);
              if (itemMetadata) {
                metadataCell.append(itemMetadata);
              }
            }
          });

          columnsDiv.append(columnsTable);
          infoContainer.append(columnsDiv);
        }

        return infoContainer;
      },
    }),
  );
}

function getItemMetadata(
  table: DataTable,
  column: DataTable["columns"][0],
): HTMLSpanElement | undefined {
  const isPrimaryKey = table.primary_keys?.includes(column.name);
  const isIndexed = table.indexes?.includes(column.name);
  if (isPrimaryKey || isIndexed) {
    const badge = document.createElement("span");
    badge.textContent = isPrimaryKey ? "PK" : "IDX";
    badge.classList.add(
      "text-xs",
      "px-1.5",
      "py-0.5",
      "rounded-full",
      "font-medium",
      isPrimaryKey
        ? "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200"
        : "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
    );
    return badge;
  }
}

/**
 * Gets completions for variables defined in the notebook.
 */
export function getVariableCompletions(
  variables: Variables,
  skipVariables: Set<string>,
): Completion[] {
  return Object.values(variables).flatMap<Completion>((variable) => {
    if (skipVariables.has(variable.name)) {
      return [];
    }
    return {
      label: `@${variable.name}`,
      displayLabel: variable.name,
      detail: variable.dataType ?? "",
      boost: Boosts.VARIABLE,
      type: "variable",
      apply: `@${variable.name}`,
      section: "Variable",
      info: () => {
        return createVariableInfoElement(variable);
      },
    };
  });
}

function createVariableInfoElement(variable: Variable): HTMLElement {
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

  // Variable header
  const header = document.createElement("div");
  header.classList.add("flex", "items-center", "gap-2");

  const nameBadge = document.createElement("span");
  nameBadge.classList.add("font-bold", "text-base");
  nameBadge.textContent = variable.name;
  header.append(nameBadge);

  if (variable.dataType) {
    const typeBadge = document.createElement("span");
    typeBadge.classList.add(
      "text-xs",
      "px-1.5",
      "py-0.5",
      "rounded-full",
      "bg-purple-100",
      "text-purple-800",
      "dark:bg-purple-900",
      "dark:text-purple-200",
    );
    typeBadge.textContent = variable.dataType;
    header.append(typeBadge);
  }

  infoContainer.append(header);

  // Variable value
  if (variable.value) {
    const valueContainer = document.createElement("div");
    valueContainer.classList.add("flex", "flex-col", "gap-1");

    const valueLabel = document.createElement("div");
    valueLabel.classList.add("text-xs", "text-muted-foreground");
    valueLabel.textContent = "Value:";
    valueContainer.append(valueLabel);

    const valueContent = document.createElement("div");
    valueContent.classList.add(
      "text-xs",
      "font-mono",
      "bg-muted",
      "p-2",
      "rounded",
      "overflow-auto",
      "max-h-40",
    );
    valueContent.textContent = variable.value;
    valueContainer.append(valueContent);

    infoContainer.append(valueContainer);
  }

  return infoContainer;
}
