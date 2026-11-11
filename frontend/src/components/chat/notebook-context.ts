/* Copyright 2026 Marimo. All rights reserved. */

import type { DataUIPart, UIMessage } from "ai";
import { z } from "zod";

const notebookContextSchema = z.object({
  sessionId: z.string(),
  cells: z.array(z.object({ id: z.string(), code: z.string() })).optional(),
  cellIds: z.array(z.string()).optional(),
});

type NotebookContext = z.infer<typeof notebookContextSchema>;
type NotebookContextPart = DataUIPart<{
  "marimo-notebook": NotebookContext;
}>;

export const NOTEBOOK_CONTEXT_PART_TYPE =
  "data-marimo-notebook" as const satisfies NotebookContextPart["type"];

interface NotebookSnapshot {
  sessionId: string;
  cells?: Readonly<Record<string, string>>;
}

export function withNotebookContext(
  parts: UIMessage["parts"],
  history: UIMessage[],
  snapshot: NotebookSnapshot,
): UIMessage["parts"] {
  let cellIds: string[] | undefined;
  const cells = new Map<string, string>();
  for (const message of history) {
    if (message.role !== "user") {
      continue;
    }
    for (const part of message.parts) {
      if (part.type !== NOTEBOOK_CONTEXT_PART_TYPE) {
        continue;
      }
      const parsed = notebookContextSchema.safeParse(part.data);
      if (!parsed.success) {
        continue;
      }
      if (parsed.data.cellIds) {
        cellIds = parsed.data.cellIds;
        const retained = new Set(cellIds);
        for (const id of cells.keys()) {
          if (!retained.has(id)) {
            cells.delete(id);
          }
        }
      }
      for (const cell of parsed.data.cells ?? []) {
        cells.set(cell.id, cell.code);
      }
    }
  }

  const update: NotebookContext = { sessionId: snapshot.sessionId };
  if (snapshot.cells) {
    const nextIds = Object.keys(snapshot.cells);
    if (
      !cellIds ||
      nextIds.length !== cellIds.length ||
      nextIds.some((id, index) => id !== cellIds[index])
    ) {
      update.cellIds = nextIds;
    }
    const changed = Object.entries(snapshot.cells)
      .filter(([id, code]) => cells.get(id) !== code)
      .map(([id, code]) => ({ id, code }));
    update.cells = changed;
  }

  const context: NotebookContextPart = {
    type: NOTEBOOK_CONTEXT_PART_TYPE,
    data: update,
  };
  return [context, ...parts];
}
