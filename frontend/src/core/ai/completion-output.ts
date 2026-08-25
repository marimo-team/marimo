/* Copyright 2026 Marimo. All rights reserved. */

import type { DataUIPart, UIMessage, UIMessageChunk } from "ai";
import { z } from "zod";

// Mirrored from marimo/_server/ai/completion_output.py; SSE data parts are not
// represented in OpenAPI.
const CELL_COMPLETION_DATA_PART = "cell-completion" as const;
const NOTEBOOK_CELLS_COMPLETION_DATA_PART =
  "notebook-cells-completion" as const;

export const CELL_COMPLETION_DATA_TYPE =
  `data-${CELL_COMPLETION_DATA_PART}` as const;
export const NOTEBOOK_CELLS_COMPLETION_DATA_TYPE =
  `data-${NOTEBOOK_CELLS_COMPLETION_DATA_PART}` as const;

export const cellCompletionSchema = z.object({
  code: z.string(),
});

export const generatedCellSchema = z.object({
  language: z.enum(["python", "sql", "markdown"]),
  code: z.string(),
});

export const notebookCellsCompletionSchema = z.object({
  cells: z.array(generatedCellSchema),
});

export type CellCompletion = z.infer<typeof cellCompletionSchema>;
export type GeneratedCell = z.infer<typeof generatedCellSchema>;
export type NotebookCellsCompletion = z.infer<
  typeof notebookCellsCompletionSchema
>;

const completionDataSchemas = {
  [CELL_COMPLETION_DATA_PART]: cellCompletionSchema,
  [NOTEBOOK_CELLS_COMPLETION_DATA_PART]: notebookCellsCompletionSchema,
};

export type CompletionDataParts = {
  [Name in keyof typeof completionDataSchemas]: z.infer<
    (typeof completionDataSchemas)[Name]
  >;
};

export type CompletionUIMessage = UIMessage<unknown, CompletionDataParts>;
export type CompletionDataPart = DataUIPart<CompletionDataParts>;

type DataChunk = Extract<UIMessageChunk, { type: `data-${string}` }>;

export function isDataChunk(chunk: UIMessageChunk): chunk is DataChunk {
  return chunk.type.startsWith("data-");
}
