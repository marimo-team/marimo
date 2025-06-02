/* Copyright 2024 Marimo. All rights reserved. */
import { getCodes } from "@/core/codemirror/copilot/getCodes";
import { allTablesAtom } from "@/core/datasets/data-source-connections";
import type { DataTable } from "@/core/kernel/messages";
import type { AiCompletionRequest } from "@/core/network/types";
import { store } from "@/core/state/jotai";
import { variablesAtom } from "@/core/variables/state";
import type { Variable, VariableName } from "@/core/variables/types";
import { Logger } from "@/utils/Logger";
import type {
  CompletionSource,
  Completion,
  CompletionContext,
} from "@codemirror/autocomplete";

/**
 * Gets the request body for the AI completion API.
 */
export function getAICompletionBody({
  input,
}: { input: string }): Omit<
  AiCompletionRequest,
  "language" | "prompt" | "code"
> {
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
  const allTables = store.get(allTablesAtom);
  const allVariables = store.get(variablesAtom);

  // Extract mentions from the input
  const mentions = input.match(/@([\w.]+)/g) || [];
  const mentionedNames = mentions.map((mention) => mention.slice(1));

  const datasets: DataTable[] = [];
  const variables: Variable[] = [];

  for (const name of mentionedNames) {
    // First process datasets (higher priority)
    const dataset = allTables.get(name);
    if (dataset) {
      datasets.push(dataset);
      continue;
    }

    // Then process variables if not already processed as datasets
    const variable = allVariables[name as VariableName];
    if (variable) {
      variables.push(variable);
    }
  }

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

/**
 * Parses the completion content string and extracts only text parts.
 * Ignores reasoning tokens (g: prefix).
 * Returns concatenated text content as a string.
 */
export const parseCompletionContent = (completion: string): string => {
  if (!completion) {
    return "";
  }

  let textContent = "";
  const lines = completion.split("\n");

  for (const line of lines) {
    if (!line.trim()) {
      continue;
    }

    // Parse text content (0: prefix)
    if (line.startsWith("0:")) {
      try {
        const content = JSON.parse(line.slice(2));
        if (content && typeof content === "string") {
          textContent += content;
        }
      } catch {
        // If JSON parsing fails, treat the rest as raw content
        const content = line.slice(2);
        if (content) {
          textContent += content;
        }
      }
    }
    // Skip reasoning content (g: prefix) - we ignore it
    else if (line.startsWith("g:")) {
      // Intentionally skip reasoning content
    }
    // Handle content without prefix as text
    else {
      textContent += `${line}\n`;
    }
  }

  // Remove markdown code fences
  return (
    textContent
      // Remove opening fences for python, py, and sql
      .replaceAll(/^```(?:python|py|sql)?\s*\n?/gm, "")
      // Remove closing fences
      .replaceAll(/^```\s*$/gm, "")
      .trimEnd()
  );
};
