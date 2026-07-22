/* Copyright 2026 Marimo. All rights reserved. */

import type { Completion } from "@codemirror/autocomplete";
import {
  type CellErrorEntry,
  describeError,
  formatSingleError,
  getCellErrorEntries,
} from "@/core/errors/error-entries";
import type { JotaiStore } from "@/core/state/jotai";
import { parseHtmlContent } from "@/utils/dom";
import { PluralWord } from "@/utils/pluralize";
import { type AIContextItem, AIContextProvider } from "../registry";
import { contextToXml } from "../utils";
import { Sections } from "./common";
import { formatDatasourceContextForCell } from "./datasource";

export type ErrorContextItemData =
  | {
      type: "all-errors";
      errors: CellErrorEntry[];
    }
  | {
      type: "cell-error";
      error: CellErrorEntry;
    };

export interface ErrorContextItem extends AIContextItem {
  type: "error";
  data: ErrorContextItemData;
}

function formatCellErrorDetails(
  entry: CellErrorEntry,
  store: JotaiStore,
): string {
  const parts: string[] = [`Code:\n${entry.cellCode}`];

  if (entry.tracebackHtml) {
    parts.push(`Traceback:\n${parseHtmlContent(entry.tracebackHtml)}`);
  }

  if (entry.errorData.length > 0) {
    parts.push(
      entry.errorData.map((error) => formatSingleError(error)).join("\n\n"),
    );
  }

  if (entry.errorData.some((error) => error.type === "sql-error")) {
    const datasourceContext = formatDatasourceContextForCell(
      entry.cellId,
      store,
    );
    if (datasourceContext) {
      parts.push(`Database schema:\n${datasourceContext}`);
    }
  }

  return parts.join("\n\n");
}

function formatCellErrorXml(entry: CellErrorEntry, store: JotaiStore): string {
  return contextToXml({
    type: "error",
    data: {
      name: entry.cellName || `Cell ${entry.cellId}`,
      cellId: entry.cellId,
    },
    details: formatCellErrorDetails(entry, store),
  });
}

function summarizeCellError(entry: CellErrorEntry): string {
  if (entry.errorData.length === 1) {
    return describeError(entry.errorData[0]);
  }
  if (entry.errorData.length > 1) {
    return `${entry.errorData.length} errors`;
  }
  if (entry.tracebackHtml) {
    const text = parseHtmlContent(entry.tracebackHtml).trim();
    const firstLine = text
      .split("\n")
      .find((line) => line.trim())
      ?.trim();
    return firstLine || "traceback";
  }
  return "error";
}

function errorContextName(entry: CellErrorEntry): string {
  const cellName = entry.cellName || `Cell ${entry.cellId}`;
  return `Error: ${cellName}`;
}

const errorsTxt = new PluralWord("error", "errors");
export class ErrorContextProvider extends AIContextProvider<ErrorContextItem> {
  readonly title = "Errors";
  readonly mentionPrefix = "@";
  readonly contextType = "error";
  private store: JotaiStore;

  constructor(store: JotaiStore) {
    super();
    this.store = store;
  }

  getItems(): ErrorContextItem[] {
    const errors = getCellErrorEntries(this.store);

    if (errors.length === 0) {
      return [];
    }

    const items: ErrorContextItem[] = [
      {
        uri: this.asURI("all"),
        name: "Errors",
        type: this.contextType,
        data: {
          type: "all-errors",
          errors,
        },
        description: "All errors in the notebook",
      },
    ];

    for (const error of errors) {
      items.push({
        uri: this.asURI(error.cellId),
        name: errorContextName(error),
        type: this.contextType,
        data: {
          type: "cell-error",
          error,
        },
        description: summarizeCellError(error),
      });
    }

    return items;
  }

  formatCompletion(item: ErrorContextItem): Completion {
    if (item.data.type === "all-errors") {
      const errorCount = item.data.errors.length;
      return {
        label: "@Errors",
        displayLabel: "Errors",
        detail: `${errorCount} ${errorsTxt.pluralize(errorCount)}`,
        type: "error",
        apply: "@error://all",
        section: Sections.ERROR,
        info: () => {
          const infoContainer = document.createElement("div");
          infoContainer.classList.add(
            "mo-cm-tooltip",
            "docs-documentation",
            "min-w-[200px]",
            "flex",
            "flex-col",
            "gap-1",
            "p-2",
          );

          const headerDiv = document.createElement("div");
          headerDiv.classList.add("flex", "flex-col", "gap-1");

          const nameDiv = document.createElement("div");
          nameDiv.classList.add("font-bold", "text-base");
          nameDiv.textContent = "Errors";
          headerDiv.append(nameDiv);

          const descriptionDiv = document.createElement("div");
          descriptionDiv.classList.add("text-sm", "text-muted-foreground");
          descriptionDiv.textContent = `${errorCount} ${errorsTxt.pluralize(errorCount)}`;
          headerDiv.append(descriptionDiv);

          infoContainer.append(headerDiv);

          return infoContainer;
        },
      };
    }

    if (item.data.type === "cell-error") {
      const { error } = item.data;
      return {
        ...this.createBasicCompletion(item, {
          detail: summarizeCellError(error),
          type: "error",
        }),
        section: Sections.ERROR,
      };
    }

    return {
      label: "Error",
      displayLabel: "Error",
      section: Sections.ERROR,
    };
  }

  formatContext(item: ErrorContextItem): string {
    const entries =
      item.data.type === "all-errors" ? item.data.errors : [item.data.error];

    return entries
      .map((entry) => formatCellErrorXml(entry, this.store))
      .join("\n\n");
  }
}
