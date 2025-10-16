/* Copyright 2024 Marimo. All rights reserved. */

import type { EditorView } from "@codemirror/view";
import { z } from "zod";
import { scrollAndHighlightCell } from "@/components/editor/links/cell-link";
import {
  createNotebookActions,
  type CellPosition as NotebookCellPosition,
  type NotebookState,
  notebookAtom,
  notebookReducer,
} from "@/core/cells/cells";
import { CellId } from "@/core/cells/ids";
import { updateEditorCodeFromPython } from "@/core/codemirror/language/utils";
import type { JotaiStore } from "@/core/state/jotai";
import type { CellColumnId } from "@/utils/id-tree";
import {
  createStagedAICellsActions,
  stagedAICellsAtom,
  stagedAICellsReducer,
} from "../staged-cells";
import {
  type AiTool,
  type ToolDescription,
  ToolExecutionError,
  type ToolOutputBase,
  toolOutputBaseSchema,
} from "./base";
import type { CopilotMode } from "./registry";

const description: ToolDescription = {
  baseDescription:
    "Perform editing operations on the current notebook. Call this tool multiple times to perform multiple edits.",
  prerequisites: [
    "Find out the cellIds and columnIds first (call get_lightweight_cell_map tool)",
  ],
  additionalInfo: `
  Args:
    edit (object): The editing operation to perform. Must be one of:
    - update_cell: Update the code of an existing cell, pass CellId and the new code.
    - add_cell: Add a new cell to the notebook. The position of the new cell is specified by the position argument.
        Pass "__end__" to add the new cell at the end of the notebook. 
        Pass { cellId: cellId, before: true } to add the new cell before the specified cell. And before: false if after the specified cell.
        Pass { type: "__end__", columnId: columnId } to add the new cell at the end of the specified column.
    - delete_cell: Delete an existing cell, pass CellId.

    Returns:
    - A result object containing standard tool metadata.`,
};

type CellPosition =
  | { cellId: CellId; before: boolean }
  | { type: "__end__"; columnId: CellColumnId }
  | "__end__";

const editNotebookSchema = z.object({
  edit: z.discriminatedUnion("type", [
    z.object({
      type: z.literal("update_cell"),
      cellId: z.string() as unknown as z.ZodType<CellId>,
      code: z.string(),
    }),
    z.object({
      type: z.literal("add_cell"),
      position: z.union([
        z.object({
          cellId: z.string() as unknown as z.ZodType<CellId>,
          before: z.boolean(),
        }),
        z.object({
          type: z.literal("__end__"),
          columnId: z.string() as unknown as z.ZodType<CellColumnId>,
        }),
        z.literal("__end__"),
      ]) satisfies z.ZodType<CellPosition>,
      code: z.string(),
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
  private readonly notebookActions: ReturnType<typeof createNotebookActions>;
  private readonly stagedAICellsActions: ReturnType<
    typeof createStagedAICellsActions
  >;
  readonly name = "edit_notebook_tool";
  readonly description = description;
  readonly schema = editNotebookSchema;
  readonly outputSchema = toolOutputBaseSchema;
  readonly mode: CopilotMode[] = ["agent"];

  constructor(store: JotaiStore) {
    this.store = store;
    this.notebookActions = createNotebookActions((action) => {
      this.store.set(notebookAtom, (state) => notebookReducer(state, action));
    });
    this.stagedAICellsActions = createStagedAICellsActions((action) => {
      this.store.set(stagedAICellsAtom, (state) =>
        stagedAICellsReducer(state, action),
      );
    });
  }

  handler = async ({ edit }: EditNotebookInput): Promise<ToolOutputBase> => {
    switch (edit.type) {
      case "update_cell": {
        const { cellId, code } = edit;

        const notebook = this.store.get(notebookAtom);
        this.validateCellIdExists(cellId, notebook);
        const editorView = this.getCellEditorView(cellId, notebook);

        scrollAndHighlightCell(cellId);

        const currentCellCode = editorView.state.doc.toString();
        this.stagedAICellsActions.addStagedCell({
          cellId,
          edit: { type: "update_cell", previousCode: currentCellCode },
        });

        updateEditorCodeFromPython(editorView, code);

        break;
      }
      case "add_cell": {
        const { position, code } = edit;

        // By default, add the new cell to the end of the notebook
        let notebookPosition: NotebookCellPosition = "__end__";
        let before = false;
        const newCellId = CellId.create();

        if (typeof position === "object") {
          const notebook = this.store.get(notebookAtom);
          if ("cellId" in position) {
            this.validateCellIdExists(position.cellId, notebook);
            notebookPosition = position.cellId;
            before = position.before;
          } else if ("columnId" in position) {
            this.validateColumnIdExists(position.columnId, notebook);
            notebookPosition = { type: "__end__", columnId: position.columnId };
          }
        }

        this.notebookActions.createNewCell({
          cellId: notebookPosition,
          before,
          code,
          newCellId,
        });

        // Add to staged AICells
        this.stagedAICellsActions.addStagedCell({
          cellId: newCellId,
          edit: { type: "add_cell" },
        });

        // Scroll into view
        scrollAndHighlightCell(newCellId);

        break;
      }
      case "delete_cell": {
        const { cellId } = edit;
        const notebook = this.store.get(notebookAtom);
        this.validateCellIdExists(cellId, notebook);

        const editorView = this.getCellEditorView(cellId, notebook);
        const currentCellCode = editorView.state.doc.toString();

        // Add to staged AICells
        this.stagedAICellsActions.addStagedCell({
          cellId,
          edit: { type: "delete_cell", previousCode: currentCellCode },
        });

        this.notebookActions.deleteCell({ cellId });
        break;
      }
    }
    return {
      status: "success",
      next_steps: ["If you need to perform more edits, call this tool again."],
    };
  };

  private validateCellIdExists(cellId: CellId, notebook: NotebookState) {
    const cellIds = notebook.cellIds;
    if (!cellIds.getColumns().some((column) => column.idSet.has(cellId))) {
      throw new ToolExecutionError(
        "Cell not found",
        "CELL_NOT_FOUND",
        false,
        "Check which cells exist in the notebook",
      );
    }
  }

  private validateColumnIdExists(
    columnId: CellColumnId,
    notebook: NotebookState,
  ) {
    const cellIds = notebook.cellIds;
    if (!cellIds.getColumns().some((column) => column.id === columnId)) {
      throw new ToolExecutionError(
        "Column not found",
        "COLUMN_NOT_FOUND",
        false,
        "Check which columns exist in the notebook",
      );
    }
  }

  private getCellEditorView(
    cellId: CellId,
    notebook: NotebookState,
  ): EditorView {
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
    return cellHandle.editorView;
  }
}
