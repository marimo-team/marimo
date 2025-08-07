/* Copyright 2024 Marimo. All rights reserved. */

import type { Completion } from "@codemirror/autocomplete";
import { getVariableCompletions } from "@/core/codemirror/completion/variable-completions";
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
