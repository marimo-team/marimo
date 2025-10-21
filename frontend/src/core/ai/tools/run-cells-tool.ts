/* Copyright 2024 Marimo. All rights reserved. */

import type { FileUIPart } from "ai";
import { z } from "zod";
import { runCells } from "@/components/editor/cell/useRunCells";
import { notebookAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { staleCellIds } from "@/core/cells/utils";
import { type JotaiStore, waitFor } from "@/core/state/jotai";
import {
  type BaseOutput,
  getCellContextData,
} from "../context/providers/cell-output";
import {
  type AiTool,
  type EmptyToolInput,
  type ToolDescription,
  type ToolNotebookContext,
  type ToolOutputBase,
  toolOutputBaseSchema,
} from "./base";
import type { CopilotMode } from "./registry";

interface CellOutput {
  consoleOutput?: string;
  // consoleAttachments?: FileUIPart[];
  cellOutput?: string;
  // cellAttachments?: FileUIPart[];
}

// Must use Record instead of Map because Map serializes to JSON as {}
interface RunStaleCellsOutput extends ToolOutputBase {
  cellsToOutput?: Record<CellId, CellOutput | null>;
}

const description: ToolDescription = {
  baseDescription:
    "Run cells in the current notebook that are stale. Stale cells are cells that have been edited or newly added. You can run this tool after editing the notebook or when requested. The output of the ran cells will be returned alongside metadata.",
};

const filePartSchema = z.object({
  type: z.literal("file"),
  url: z.string(),
  mediaType: z.string(),
}) satisfies z.ZodType<FileUIPart>;

export class RunStaleCellsTool
  implements AiTool<EmptyToolInput, RunStaleCellsOutput>
{
  readonly name = "run_stale_cells_tool";
  readonly description = description;
  readonly schema = z.object({});
  readonly outputSchema = toolOutputBaseSchema.extend({
    cellsToOutput: z
      .record(
        z.string(),
        z
          .object({
            consoleOutput: z.string().optional(),
            cellOutput: z.string().optional(),
            consoleAttachments: z.array(filePartSchema).optional(),
            cellAttachments: z.array(filePartSchema).optional(),
          })
          .nullable(),
      )
      .optional(),
  }) satisfies z.ZodType<RunStaleCellsOutput>;
  readonly mode: CopilotMode[] = ["agent"];
  private store: JotaiStore;

  constructor(store: JotaiStore) {
    this.store = store;
  }

  handler = async (
    _args: EmptyToolInput,
    toolContext: ToolNotebookContext,
  ): Promise<RunStaleCellsOutput> => {
    const { prepareForRun, sendRun } = toolContext;

    const notebook = this.store.get(notebookAtom);
    const staleCells = staleCellIds(notebook);

    if (staleCells.length === 0) {
      return {
        status: "success",
        message: "No stale cells found.",
      };
    }

    await runCells({
      cellIds: staleCells,
      sendRun: sendRun,
      prepareForRun,
      notebook,
    });

    // Wait for all cells to finish executing
    const allCellsFinished = await this.waitForCellsToFinish(staleCells);
    if (!allCellsFinished) {
      return {
        status: "success",
        message:
          "No output was returned because some cells have not finished executing",
      };
    }

    // Get notebook state after cells have finished
    const updatedNotebook = this.store.get(notebookAtom);

    const cellsToOutput = new Map<CellId, CellOutput | null>();
    let resultMessage = "";

    for (const cellId of staleCells) {
      const cellContextData = getCellContextData(cellId, updatedNotebook, {
        includeConsoleOutput: true,
      });

      let cellOutputString: string | undefined;
      // let cellAttachments: FileUIPart[] | undefined;
      let consoleOutputString: string | undefined;
      // let consoleAttachments: FileUIPart[] | undefined;

      const cellOutput = cellContextData.cellOutput;
      const consoleOutputs = cellContextData.consoleOutputs;
      if (!cellOutput && !consoleOutputs) {
        // Set null to show no output
        cellsToOutput.set(cellId, null);
        continue;
      }

      if (cellOutput) {
        cellOutputString = this.formatOutputString(cellOutput);
        // cellAttachments = await getAttachmentsForOutputs(
        //   [cellOutput],
        //   cellId,
        //   cellContextData.cellName,
        // );
      }

      if (consoleOutputs) {
        // consoleAttachments = await getAttachmentsForOutputs(
        //   consoleOutputs,
        //   cellId,
        //   cellContextData.cellName,
        // );
        consoleOutputString = consoleOutputs
          .map((output) => this.formatOutputString(output))
          .join("\n");
        resultMessage +=
          "Console output represents the stdout or stderr of the cell (eg. print statements).";
      }

      cellsToOutput.set(cellId, {
        cellOutput: cellOutputString,
        consoleOutput: consoleOutputString,
        // cellAttachments: cellAttachments,
        // consoleAttachments: consoleAttachments,
      });
    }

    if (cellsToOutput.size === 0) {
      return {
        status: "success",
        message: "Stale cells have been run. No output was returned.",
      };
    }

    return {
      status: "success",
      cellsToOutput: Object.fromEntries(cellsToOutput),
      message: resultMessage === "" ? undefined : resultMessage,
    };
  };

  private formatOutputString(cellOutput: BaseOutput): string {
    let outputString = "";
    const { outputType, processedContent, imageUrl, output } = cellOutput;
    if (outputType === "text" && processedContent) {
      outputString += `Output:\n${processedContent}`;
    } else if (outputType === "media") {
      outputString += `Media Output: Contains ${output.mimetype} content`;
      if (imageUrl) {
        outputString += `\nImage URL: ${imageUrl}`;
      }
    }
    return outputString;
  }

  /**
   * Wait for cells to finish executing (status becomes "idle")
   * Returns true if all cells finished executing, false if the timeout was reached
   */
  private async waitForCellsToFinish(
    cellIds: CellId[],
    timeout = 30_000,
  ): Promise<boolean> {
    const checkAllFinished = (
      notebook: ReturnType<typeof notebookAtom.read>,
    ) => {
      return cellIds.every((cellId) => {
        const cellRuntime = notebook.cellRuntime[cellId];
        return (
          cellRuntime?.status !== "running" && cellRuntime?.status !== "queued"
        );
      });
    };

    // If already finished, return immediately
    if (checkAllFinished(this.store.get(notebookAtom))) {
      return true;
    }

    // Wait for notebook state changes with timeout
    try {
      await Promise.race([
        waitFor(notebookAtom, checkAllFinished),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error("timeout")), timeout),
        ),
      ]);
      return true;
    } catch {
      return false;
    }
  }
}
