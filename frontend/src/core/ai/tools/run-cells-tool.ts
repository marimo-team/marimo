/* Copyright 2026 Marimo. All rights reserved. */

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

const POST_EXECUTION_DELAY = 200;
const WAIT_FOR_CELLS_TIMEOUT = 30_000;

interface CellOutput {
  consoleOutput?: string;
  cellOutput?: string;
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

  private readonly postExecutionDelay: number;

  constructor(opts?: { postExecutionDelay?: number }) {
    this.postExecutionDelay = opts?.postExecutionDelay ?? POST_EXECUTION_DELAY;
  }

  handler = async (
    _args: EmptyToolInput,
    toolContext: ToolNotebookContext,
  ): Promise<RunStaleCellsOutput> => {
    const { prepareForRun, sendRun, store } = toolContext;

    const notebook = store.get(notebookAtom);
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
    const allCellsFinished = await this.waitForCellsToFinish(
      store,
      staleCells,
      WAIT_FOR_CELLS_TIMEOUT,
      this.postExecutionDelay,
    );
    if (!allCellsFinished) {
      return {
        status: "success",
        message:
          "No output was returned because some cells have not finished executing",
      };
    }

    // Get notebook state after cells have finished
    const updatedNotebook = store.get(notebookAtom);

    const cellsToOutput = new Map<CellId, CellOutput | null>();
    let resultMessage = "";
    let outputHasErrors = false;

    for (const cellId of staleCells) {
      const cellContextData = getCellContextData(cellId, updatedNotebook, {
        includeConsoleOutput: true,
      });

      let cellOutputString: string | undefined;
      let consoleOutputString: string | undefined;

      const cellOutput = cellContextData.cellOutput;
      const consoleOutputs = cellContextData.consoleOutputs;
      const hasConsoleOutput = consoleOutputs && consoleOutputs.length > 0;

      if (!cellOutput && !hasConsoleOutput) {
        // Set null to show no output
        cellsToOutput.set(cellId, null);
        continue;
      }

      if (cellOutput) {
        cellOutputString = this.formatOutputString(cellOutput);
        if (this.outputHasErrors(cellOutput)) {
          outputHasErrors = true;
        }
      }

      if (hasConsoleOutput) {
        consoleOutputString = consoleOutputs
          .map((output) => this.formatOutputString(output))
          .join("\n");
        resultMessage +=
          "Console output represents the stdout or stderr of the cell (eg. print statements).";

        if (consoleOutputs.some((output) => this.outputHasErrors(output))) {
          outputHasErrors = true;
        }
      }

      cellsToOutput.set(cellId, {
        cellOutput: cellOutputString,
        consoleOutput: consoleOutputString,
      });
    }

    if (cellsToOutput.size === 0) {
      return {
        status: "success",
        message: "Stale cells have been run. No output was returned.",
      };
    }

    const nextSteps = [
      "Review the output of the cells. The CellId is the key of the result object.",
      outputHasErrors
        ? "There are errors in the cells. Please fix them by using the edit notebook tool and the given CellIds."
        : "You may edit the notebook further with the given CellIds.",
    ];

    return {
      status: "success",
      cellsToOutput: Object.fromEntries(cellsToOutput),
      message: resultMessage === "" ? undefined : resultMessage,
      next_steps: nextSteps,
    };
  };

  private outputHasErrors(cellOutput: BaseOutput): boolean {
    const { output } = cellOutput;
    if (
      output.mimetype === "application/vnd.marimo+error" ||
      output.mimetype === "application/vnd.marimo+traceback"
    ) {
      return true;
    }
    return false;
  }

  private formatOutputString(cellOutput: BaseOutput): string {
    let outputString = "";
    const { outputType, processedContent, imageUrl, output } = cellOutput;
    if (outputType === "text") {
      outputString += "Output:\n";
      if (processedContent) {
        outputString += processedContent;
      } else if (typeof output.data === "string") {
        outputString += output.data;
      } else {
        outputString += JSON.stringify(output.data);
      }
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
    store: JotaiStore,
    cellIds: CellId[],
    timeout: number,
    postExecutionDelay: number,
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

    // Add a small delay after cells finish to allow console outputs to arrive
    // Console outputs are streamed and might still be in-flight
    const delayForConsoleOutputs = async () => {
      if (postExecutionDelay > 0) {
        await new Promise((resolve) => setTimeout(resolve, postExecutionDelay));
      }
      return true;
    };

    // Return immediately if all cells are finished
    if (checkAllFinished(store.get(notebookAtom))) {
      return await delayForConsoleOutputs();
    }

    // Wait for notebook state changes with timeout
    try {
      await Promise.race([
        waitFor(notebookAtom, checkAllFinished),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error("timeout")), timeout),
        ),
      ]);
      return await delayForConsoleOutputs();
    } catch {
      return false;
    }
  }
}
