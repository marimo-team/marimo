/* Copyright 2024 Marimo. All rights reserved. */
import { getCodes } from "@/core/codemirror/copilot/getCodes";
import { dataSourceConnectionsAtom } from "@/core/datasets/data-source-connections";
import { datasetTablesAtom } from "@/core/datasets/state";
import type { DataTable } from "@/core/kernel/messages";
import type { AiCompletionRequest } from "@/core/network/types";
import { store } from "@/core/state/jotai";
import { Logger } from "@/utils/Logger";
import { Maps } from "@/utils/maps";
import {
  autocompletion,
  type Completion,
  type CompletionContext,
} from "@codemirror/autocomplete";
import type { Extension } from "@codemirror/state";

/**
 * Gets the request body for the AI completion API.
 */
export function getAICompletionBody(
  input: string,
): Omit<AiCompletionRequest, "language" | "prompt" | "code"> {
  const datasets = extractDatasets(input);
  Logger.debug("Included datasets", datasets);

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
    },
  };
}

/**
 * Extracts datasets from the input.
 * Datasets are referenced with @<dataset_name> in the input.
 */
function extractDatasets(input: string): DataTable[] {
  const datasets = store.get(datasetTablesAtom);
  const connectionsMap = store.get(dataSourceConnectionsAtom).connectionsMap;
  const connections = [...connectionsMap.values()];
  const allTables = [
    ...datasets,
    ...connections.flatMap((c) =>
      c.databases.flatMap((d) => d.schemas.flatMap((s) => s.tables)),
    ),
  ];
  // TODO: This does not handle duplicates table names.
  const existingDatasets = Maps.keyBy(allTables, (dataset) => dataset.name);

  // Extract dataset mentions from the input
  const mentionedDatasets = input.match(/@([\w.]+)/g) || [];

  // Filter to only include datasets that exist
  return mentionedDatasets
    .map((mention) => mention.slice(1))
    .map((name) => existingDatasets.get(name))
    .filter(Boolean);
}

/**
 * Adapted from @uiw/codemirror-extensions-mentions
 * Allows you to specify a custom regex to trigger the autocompletion.
 */
export function mentions(
  matchBeforeRegexes: RegExp[],
  data: Completion[] = [],
): Extension {
  return autocompletion({
    override: [
      (context: CompletionContext) => {
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
      },
    ],
  });
}
