/* Copyright 2024 Marimo. All rights reserved. */

import type { Completion } from "@codemirror/autocomplete";
import { createVariableInfoElement } from "@/core/codemirror/completion/variable-completions";
import type { DatasetTablesMap } from "@/core/datasets/data-source-connections";
import type { Variable, Variables } from "@/core/variables/types";
import { type AIContextItem, AIContextProvider } from "../registry";
import { Boosts } from "./common";

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
    const ignore = new Set(this.tablesMap.keys());

    return Object.entries(this.variables).flatMap(([name, variable]) => {
      if (ignore.has(name)) {
        return [];
      }
      return [
        {
          uri: this.asURI(name),
          name: name,
          type: this.contextType,
          description: variable.dataType ?? "",
          dataType: variable.dataType,
          data: {
            variable,
          },
        },
      ];
    });
  }

  formatCompletion(item: VariableContextItem): Completion {
    const { data } = item;
    const { variable } = data;
    return {
      label: `@${variable.name}`,
      displayLabel: variable.name,
      detail: variable.dataType ?? "",
      boost: Boosts.VARIABLE,
      type: this.contextType,
      section: "Variable",
      info: () => {
        return createVariableInfoElement(variable);
      },
    };
  }

  formatContext(item: VariableContextItem): string {
    const { uri: id, data } = item;
    const { variable } = data;
    return `Variable: ${id}\nType: ${variable.dataType || "unknown"}\nPreview: ${JSON.stringify(variable.value)}`;
  }

  getCompletions(): Completion[] {
    return [];
  }
}
