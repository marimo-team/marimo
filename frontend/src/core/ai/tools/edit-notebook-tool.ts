/* Copyright 2024 Marimo. All rights reserved. */

import { z } from "zod";
import { notebookAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { updateEditorCodeFromPython } from "@/core/codemirror/language/utils";
import type { JotaiStore } from "@/core/state/jotai";
import { stagedAICellsAtom } from "../staged-cells";
import {
  type AiTool,
  ToolExecutionError,
  type ToolOutputBase,
  toolOutputBaseSchema,
} from "./base";
import type { CopilotMode } from "./registry";

const description = `
Perform editing operations on the current notebook. 
Call this tool multiple times to perform multiple edits.

Args:
- edit (object): The editing operation to perform. Must be one of:
    - update_cell: Update the code of an existing cell.
    - add_cell: Add a new cell to the notebook.
    - delete_cell: Delete an existing cell.

Returns:
- A result object containing standard tool metadata.
`;

const editNotebookSchema = z.object({
  edit: z.discriminatedUnion("type", [
    z.object({
      type: z.literal("update_cell"),
      cellId: z.string() as unknown as z.ZodType<CellId>,
      code: z.string(),
    }),
    z.object({
      type: z.literal("add_cell"),
      cellId: z.string() as unknown as z.ZodType<CellId>,
      code: z.string(),
      language: z.enum(["python", "sql", "markdown"]).optional(),
    }),
    z.object({
      type: z.literal("delete_cell"),
      cellId: z.string() as unknown as z.ZodType<CellId>,
    }),
  ]),
});

type EditNotebookInput = z.infer<typeof editNotebookSchema>;
type EditOperation = EditNotebookInput["edit"];
export type EditType = EditOperation["type"];

export class EditNotebookTool
  implements AiTool<EditNotebookInput, ToolOutputBase>
{
  private readonly store: JotaiStore;
  readonly name = "edit_notebook_tool";
  readonly description = description;
  readonly schema = editNotebookSchema;
  readonly outputSchema = toolOutputBaseSchema;
  readonly mode: CopilotMode[] = ["agent"];

  constructor(store: JotaiStore) {
    this.store = store;
  }

  handler = async ({ edit }: EditNotebookInput): Promise<ToolOutputBase> => {
    switch (edit.type) {
      case "update_cell": {
        const { cellId, code } = edit;

        const notebook = this.store.get(notebookAtom);
        const cellIds = notebook.cellIds;
        if (!cellIds.getColumns().some((column) => column.idSet.has(cellId))) {
          throw new ToolExecutionError(
            "Cell not found",
            "CELL_NOT_FOUND",
            false,
            "Check which cells exist in the notebook",
          );
        }

        const cellHandles = notebook.cellHandles;
        const cellHandle = cellHandles[cellId].current;
        if (!cellHandle?.editorView) {
          throw new ToolExecutionError(
            "Cell editor not found",
            "CELL_EDITOR_NOT_FOUND",
            false,
            "Internal error, ask the user to report this error",
          );
        }

        const currentCellCode = cellHandle.editorView.state.doc.toString();

        const stagedAICells = this.store.get(stagedAICellsAtom);
        const newStagedAICells = new Map([
          ...stagedAICells,
          [cellId, { type: "update_cell", previousCode: currentCellCode }],
        ]);
        this.store.set(stagedAICellsAtom, newStagedAICells);

        updateEditorCodeFromPython(cellHandle.editorView, code);

        break;
      }
      case "add_cell":
        // TODO
        break;
      case "delete_cell":
        // TODO
        break;
    }
    return {
      status: "success",
    };
  };
}
