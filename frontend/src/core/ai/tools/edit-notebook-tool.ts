/* Copyright 2026 Marimo. All rights reserved. */

import type { EditorView } from "@codemirror/view";
import { z } from "zod";
import { scrollAndHighlightCell } from "@/components/editor/links/cell-link";
import {
  type CellPosition as NotebookCellPosition,
  type NotebookState,
  notebookAtom,
} from "@/core/cells/cells";
import { CellId } from "@/core/cells/ids";
import { updateEditorCodeFromPython } from "@/core/codemirror/language/utils";
import type { CellColumnId } from "@/utils/id-tree";
import { stagedAICellsAtom } from "../staged-cells";
import {
  type AiTool,
  type ToolDescription,
  ToolExecutionError,
  type ToolNotebookContext,
  type ToolOutputBase,
  toolOutputBaseSchema,
} from "./base";
import type { CopilotMode } from "./registry";

const description: ToolDescription = {
  baseDescription:
    "Perform editing operations on the current notebook. You should prefer to create new cells unless you need to edit existing cells. Call this tool multiple times to perform multiple edits. Separate code into logical individual cells to take advantage of the notebook's reactive execution model.",
  prerequisites: [
    "If you are updating existing cells, you need the cellIds. If they are not known, call the lightweight_cell_map_tool to find out.",
  ],
  additionalInfo: `
  Args:
    edit (object): The editing operation to perform with the following structure:
      - type: One of "update_cell", "add_cell", or "delete_cell"
      - code (string, optional): Required for "update_cell" and "add_cell" operations. The code content for the cell.
      - position (object): Always present, with the following structure:
        - type: One of "relative", "column_end", or "notebook_end". Not needed for "delete_cell" or "update_cell" operations.
        - cellId (string, optional): Required for "update_cell", "delete_cell", and "add_cell" with "relative" position type
        - columnIndex (number, optional): Required for "add_cell" with "column_end" position type (0-based index)
        - before (boolean, optional): Required for "add_cell" with "relative" position type (true to add before, false to add after)

    Operation types:
    - update_cell: Update the code of an existing cell. Requires: code, position.cellId
    - add_cell: Add a new cell to the notebook. Requires: code, and position based on position.type:
        - position.type "notebook_end": Add at the end of the notebook (no additional position fields needed)
        - position.type "relative": Add relative to an existing cell. Requires: position.cellId, position.before
        - position.type "column_end": Add at the end of a specific column. Requires: position.columnIndex
    - delete_cell: Delete an existing cell. Requires: position.cellId. For deleting cells, the user needs to accept the deletion to actually delete the cell, so you may still see the cell in the notebook on subsequent edits which is fine.

    For adding code, use the following guidelines:
    - Markdown cells: use mo.md(f"""{content}""") function to insert content.
    - SQL cells: use mo.sql(f"""{content}""") function to insert content. If a database engine is specified, use mo.sql(f"""{content}""", engine=engine) instead.

    Returns:
    - A result object containing standard tool metadata.`,
};

const editNotebookSchema = z.object({
  edit: z.object({
    type: z.enum(["update_cell", "add_cell", "delete_cell"]),
    code: z.string().optional(),
    position: z.object({
      type: z.enum(["relative", "column_end", "notebook_end"]).optional(),
      cellId: z.string().optional(),
      columnIndex: z.number().optional(),
      before: z.boolean().optional(),
    }),
  }),
});

type EditNotebookInput = z.infer<typeof editNotebookSchema>;
type EditOperation = EditNotebookInput["edit"];
export type EditType = EditOperation["type"];

export class EditNotebookTool
  implements AiTool<EditNotebookInput, ToolOutputBase>
{
  readonly name = "edit_notebook_tool";
  readonly description = description;
  readonly schema = editNotebookSchema;
  readonly outputSchema = toolOutputBaseSchema;
  readonly mode: CopilotMode[] = ["agent"];

  handler = async (
    { edit }: EditNotebookInput,
    toolContext: ToolNotebookContext,
  ): Promise<ToolOutputBase> => {
    const { addStagedCell, createNewCell, store } = toolContext;

    switch (edit.type) {
      case "update_cell": {
        const { position, code } = edit;
        const cellId = position.cellId as CellId;

        if (!cellId) {
          throw new ToolExecutionError(
            "Cell ID is required for update_cell",
            "CELL_ID_REQUIRED_FOR_UPDATE_CELL",
            true,
            "Provide a cell ID to update",
          );
        } else if (!code) {
          throw new ToolExecutionError(
            "Code is required for update_cell",
            "CODE_REQUIRED_FOR_UPDATE_CELL",
            true,
            "Provide the new code to update the cell",
          );
        }

        const notebook = store.get(notebookAtom);
        this.validateCellIdExists(cellId, notebook);
        const editorView = this.getCellEditorView(cellId, notebook);

        scrollAndHighlightCell(cellId);

        const existingStagedCell = store.get(stagedAICellsAtom).get(cellId);

        // If previous edit was from a new cell, just replace editor code with the new code
        if (existingStagedCell?.type === "add_cell") {
          updateEditorCodeFromPython(editorView, code);
          break;
        }

        // If previous code exists, we don't want to replace it, it means there is a new edit on top of the previous update
        // Keep the original code
        const currentCellCode = editorView.state.doc.toString();
        const previousCode =
          existingStagedCell?.previousCode ?? currentCellCode;

        addStagedCell({
          cellId,
          edit: { type: "update_cell", previousCode: previousCode },
        });

        updateEditorCodeFromPython(editorView, code);

        break;
      }
      case "add_cell": {
        const { position, code } = edit;

        let notebookPosition: NotebookCellPosition = "__end__";
        let before = false;
        const newCellId = CellId.create();
        const notebook = store.get(notebookAtom);

        switch (position.type) {
          case "relative": {
            const cellId = position.cellId as CellId;
            if (!cellId) {
              throw new ToolExecutionError(
                "Cell ID is required for add_cell with relative position",
                "TOOL_ERROR",
                true,
                "Provide a cell ID to add the cell before",
              );
            }

            if (position.before === undefined) {
              throw new ToolExecutionError(
                "Before is required for add_cell with relative position",
                "TOOL_ERROR",
                true,
                `Provide a boolean value for before, true to add before cell ${cellId}, false to add after the cell`,
              );
            }

            this.validateCellIdExists(cellId, notebook);
            notebookPosition = cellId;
            before = position.before;
            break;
          }
          case "column_end": {
            if (!position.columnIndex) {
              throw new ToolExecutionError(
                "Column index is required for add_cell with column_end position",
                "TOOL_ERROR",
                true,
                "Provide a column index to add the cell at the end of",
              );
            }

            const columnId = this.getColumnId(position.columnIndex, notebook);
            notebookPosition = { type: "__end__", columnId };
            break;
          }
          case "notebook_end":
            // Use default: notebookPosition = "__end__"
            break;
        }

        createNewCell({
          cellId: notebookPosition,
          before,
          code,
          newCellId,
        });

        addStagedCell({
          cellId: newCellId,
          edit: { type: "add_cell" },
        });

        // Scroll into view
        scrollAndHighlightCell(newCellId);

        break;
      }
      case "delete_cell": {
        const { position } = edit;
        const cellId = position.cellId as CellId;

        if (!cellId) {
          throw new ToolExecutionError(
            "Cell ID is required for delete_cell",
            "CELL_ID_REQUIRED_FOR_DELETE_CELL",
            true,
            "Provide a cell ID to delete",
          );
        }

        const notebook = store.get(notebookAtom);
        this.validateCellIdExists(cellId, notebook);

        const editorView = this.getCellEditorView(cellId, notebook);
        const currentCellCode = editorView.state.doc.toString();

        // Add to staged AICells - don't actually delete the cell yet
        addStagedCell({
          cellId,
          edit: { type: "delete_cell", previousCode: currentCellCode },
        });

        scrollAndHighlightCell(cellId);
        break;
      }
    }
    return {
      status: "success",
      next_steps: [
        "If you need to perform more edits, call this tool again.",
        "You should use the lint notebook tool to check for errors and lint issues. Fix them by editing the notebook.",
        "You should use the run stale cells tool to run the cells that have been edited or newly added. This allows you to see the output of the cells and fix any errors.",
      ],
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

  private getColumnId(
    columnIndex: number,
    notebook: NotebookState,
  ): CellColumnId {
    const cellIds = notebook.cellIds;
    const columns = cellIds.getColumns();

    if (columnIndex < 0 || columnIndex >= columns.length) {
      throw new ToolExecutionError(
        "Column index is out of range",
        "COLUMN_INDEX_OUT_OF_RANGE",
        true,
        "Choose a column index between 0 and the number of columns in the notebook (0-based)",
      );
    }
    return columns[columnIndex].id;
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
