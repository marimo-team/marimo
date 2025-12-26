/* Copyright 2026 Marimo. All rights reserved. */

import type { Completion } from "@codemirror/autocomplete";
import { cellErrorsAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import type { MarimoError } from "@/core/kernel/messages";
import type { JotaiStore } from "@/core/state/jotai";
import { logNever } from "@/utils/assertNever";
import { PluralWord } from "@/utils/pluralize";
import { type AIContextItem, AIContextProvider } from "../registry";
import { contextToXml } from "../utils";
import { Sections } from "./common";

export interface ErrorContextItem extends AIContextItem {
  type: "error";
  data: {
    type: "all-errors";
    errors: {
      cellId: CellId;
      cellName: string;
      errorData: MarimoError[];
    }[];
  };
}

function describeError(error: MarimoError): string {
  if (error.type === "setup-refs") {
    return "The setup cell cannot have references";
  }
  if (error.type === "cycle") {
    return "This cell is in a cycle";
  }
  if (error.type === "multiple-defs") {
    return `The variable '${error.name}' was defined by another cell`;
  }
  if (error.type === "import-star") {
    return error.msg;
  }
  if (error.type === "ancestor-stopped") {
    return error.msg;
  }
  if (error.type === "ancestor-prevented") {
    return error.msg;
  }
  if (error.type === "exception") {
    return error.msg;
  }
  if (error.type === "strict-exception") {
    return error.msg;
  }
  if (error.type === "interruption") {
    return "This cell was interrupted and needs to be re-run";
  }
  if (error.type === "syntax") {
    return error.msg;
  }
  if (error.type === "unknown") {
    return error.msg;
  }
  if (error.type === "sql-error") {
    return error.msg;
  }
  if (error.type === "internal") {
    return error.msg || "An internal error occurred";
  }
  logNever(error);
  return "Unknown error";
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
    const errors = this.store.get(cellErrorsAtom);
    if (errors.length === 0) {
      return [];
    }

    return [
      {
        uri: this.asURI("all"),
        name: "Errors",
        type: this.contextType,
        data: {
          type: "all-errors",
          errors: errors.map((error) => ({
            cellId: error.cellId,
            cellName: error.cellName,
            errorData: error.output.data,
          })),
        },
        description: "All errors in the notebook",
      },
    ];

    // TODO: maybe handle single errors or grouped by types
  }

  formatCompletion(item: ErrorContextItem): Completion {
    if (item.data.type === "all-errors") {
      return {
        label: "@Errors",
        displayLabel: "Errors",
        detail: `${item.data.errors.length} ${errorsTxt.pluralize(item.data.errors.length)}`,
        type: "error",
        apply: "@Errors",
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
          descriptionDiv.textContent = `${item.data.errors.length} ${errorsTxt.pluralize(item.data.errors.length)}`;
          headerDiv.append(descriptionDiv);

          infoContainer.append(headerDiv);

          return infoContainer;
        },
      };
    }

    return {
      label: "Error",
      displayLabel: "Error",
      section: Sections.ERROR,
    };
  }

  formatContext(item: ErrorContextItem): string {
    const { data } = item;

    const xmls = data.errors.map((err) => {
      return contextToXml({
        type: this.contextType,
        data: {
          name: err.cellName || `Cell ${err.cellId}`,
          description: err.errorData
            .map((err) => describeError(err))
            .join("\n"),
        },
      });
    });

    const xml = xmls.join("\n\n");
    return xml;
  }
}
