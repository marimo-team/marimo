/* Copyright 2026 Marimo. All rights reserved. */

import type { DataUIPart, UIMessage, UIMessageChunk } from "ai";
import { z } from "zod";

export const CELL_COMPLETION_DATA_TYPE = "data-cell-completion" as const;
export const NOTEBOOK_CELLS_COMPLETION_DATA_TYPE =
  "data-notebook-cells-completion" as const;

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

// A type alias satisfies AI SDK's `UIDataTypes` index signature while an
// equivalent interface does not.
// oxlint-disable-next-line typescript-eslint/consistent-type-definitions
export type CompletionDataParts = {
  "cell-completion": CellCompletion;
  "notebook-cells-completion": NotebookCellsCompletion;
};

export type CompletionUIMessage = UIMessage<unknown, CompletionDataParts>;
export type CompletionDataPart = DataUIPart<CompletionDataParts>;

type DataChunk = Extract<UIMessageChunk, { type: `data-${string}` }>;

export function isDataChunk(chunk: UIMessageChunk): chunk is DataChunk {
  return chunk.type.startsWith("data-");
}
