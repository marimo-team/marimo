/* Copyright 2024 Marimo. All rights reserved. */
import { getCodes } from "@/core/codemirror/copilot/getCodes";
import { datasetTablesAtom } from "@/core/datasets/state";
import type { DataTable } from "@/core/kernel/messages";
import type { AiCompletionRequest } from "@/core/network/types";
import { store } from "@/core/state/jotai";
import { Logger } from "@/utils/Logger";
import { Maps } from "@/utils/maps";

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
  const existingDatasets = Maps.keyBy(datasets, (dataset) => dataset.name);

  // Extract dataset mentions from the input
  const mentionedDatasets = input.match(/@([\w.]+)/g) || [];

  // Filter to only include datasets that exist
  return mentionedDatasets
    .map((mention) => mention.slice(1))
    .map((name) => existingDatasets.get(name))
    .filter(Boolean);
}
