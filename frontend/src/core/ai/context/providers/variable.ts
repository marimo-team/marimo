/* Copyright 2026 Marimo. All rights reserved. */

import type { Completion } from "@codemirror/autocomplete";
import { createVariableInfoElement } from "@/core/codemirror/completion/variable-completions";
import type { DatasetTablesMap } from "@/core/datasets/data-source-connections";
import type { Variable, Variables } from "@/core/variables/types";
import { type AIContextItem, AIContextProvider } from "../registry";
import { contextToXml } from "../utils";
import { Sections } from "./common";

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

  private variables: Variables;
  private tablesMap: DatasetTablesMap;

  constructor(variables: Variables, tablesMap: DatasetTablesMap) {
    super();
    this.variables = variables;
    this.tablesMap = tablesMap;
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
      type: this.contextType,
      section: Sections.VARIABLE,
      info: () => {
        return createVariableInfoElement(variable);
      },
    };
  }

  formatContext(item: VariableContextItem): string {
    const { data } = item;
    const { variable } = data;
    return contextToXml({
      type: this.contextType,
      data: {
        name: variable.name,
        dataType: variable.dataType,
      },
      details:
        variable.value == null ? undefined : JSON.stringify(variable.value),
    });
  }
}
