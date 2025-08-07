/* Copyright 2024 Marimo. All rights reserved. */

import type {
  Completion,
  CompletionContext,
  CompletionSource,
} from "@codemirror/autocomplete";
import { getAIContextRegistry } from "@/core/ai/context/context";
import type { TableContextItem } from "@/core/ai/context/providers/tables";
import type { VariableContextItem } from "@/core/ai/context/providers/variable";
import { getCodes } from "@/core/codemirror/copilot/getCodes";
import type { DataTable } from "@/core/kernel/messages";
import type { AiCompletionRequest } from "@/core/network/types";
import { store } from "@/core/state/jotai";
import type { Variable } from "@/core/variables/types";
import { Logger } from "@/utils/Logger";

/**
 * Gets the request body for the AI completion API.
 */
export function getAICompletionBody({
  input,
}: {
  input: string;
}): Omit<AiCompletionRequest, "language" | "prompt" | "code"> {
  const { datasets, variables } = extractDatasetsAndVariables(input);
  Logger.debug("Included datasets", datasets);
  Logger.debug("Included variables", variables);

  return {
    includeOtherCode: getCodes(""),
    context: {
      schema: datasets.map((dataset) => ({
        name: dataset.name,
        columns: dataset.columns.map((column) => ({
          name: column.name,
          type: column.type,
          sampleValues: column.sample_values,
        })),
      })),
      variables: variables.map((variable) => ({
        name: variable.name,
        valueType: variable.dataType ?? "",
        previewValue: variable.value,
      })),
    },
  };
}

/**
 * Extracts datasets and variables from the input.
 * References are with @<name> in the input.
 * Prioritizes datasets over variables if there's a name conflict.
 */
function extractDatasetsAndVariables(input: string): {
  datasets: DataTable[];
  variables: Variable[];
} {
  const registry = getAIContextRegistry(store);
  const contextIds = registry.parseAllContextIds(input);
  const contextInfo = registry.getContextInfo(contextIds);
  const datasets: DataTable[] = contextInfo
    .filter((info): info is TableContextItem => info.type === "table")
    .map((info) => info.data);
  const variables: Variable[] = contextInfo
    .filter((info): info is VariableContextItem => info.type === "variable")
    .map((info) => info.data.variable);

  return { datasets, variables };
}

/**
 * Adapted from @uiw/codemirror-extensions-mentions
 * Allows you to specify a custom regex to trigger the autocompletion.
 */
export function mentionsCompletionSource(
  matchBeforeRegexes: RegExp[],
  data: Completion[] = [],
): CompletionSource {
  return (context: CompletionContext) => {
    const word = matchBeforeRegexes
      .map((regex) => context.matchBefore(regex))
      .find(Boolean);
    if (!word) {
      return null;
    }
    if (word && word.from === word.to && !context.explicit) {
      return null;
    }
    return {
      from: word?.from,
      options: [...data],
    };
  };
}
