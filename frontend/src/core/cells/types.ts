/* Copyright 2026 Marimo. All rights reserved. */

import type { Milliseconds, Seconds } from "@/utils/time";
import type { OutputMessage } from "../kernel/messages";
import type { CellConfig, RuntimeState } from "../network/types";
import type { CellId } from "./ids";
import { DEFAULT_CELL_NAME } from "./names";
import type { Outline } from "./outline";

/**
 * Whether a cell's code has changed since it last ran. A cell that never ran
 * is edited once it has code. Whitespace at the ends does not count.
 *
 * TODO(MO-8028): Temporary until staleness comes from the host's executions.
 */
export function isEdited(lastCodeRun: string | null, code: string): boolean {
  return lastCodeRun === null
    ? code.trim().length > 0
    : lastCodeRun.trim() !== code.trim();
}

/**
 * Create a new cell with default state.
 */
export function createCell({
  id,
  name = DEFAULT_CELL_NAME,
  code = "",
  lastCodeRun = null,
  lastExecutionTime = null,
  edited = false,
  config,
}: Partial<CellData> & { id: CellId }): CellData {
  return {
    id: id,
    config: config || {
      hide_code: false,
      disabled: false,
      column: null,
      expand_output: false,
    },
    name: name,
    code: code,
    edited: edited,
    lastCodeRun: lastCodeRun,
    lastExecutionTime: lastExecutionTime,
  };
}

export function createCellConfig(config?: Partial<CellConfig>): CellConfig {
  return {
    hide_code: false,
    disabled: false,
    column: null,
    expand_output: false,
    ...config,
  };
}

export function createCellRuntimeState(
  state?: Partial<CellRuntimeState>,
): CellRuntimeState {
  return {
    outline: null,
    output: null,
    consoleOutputs: [],
    status: "idle" as RuntimeState,
    staleInputs: false,
    interrupted: false,
    errored: false,
    stopped: false,
    runElapsedTimeMs: null,
    runStartTimestamp: null,
    lastRunStartTimestamp: null,
    debuggerActive: false,
    ...state,
  };
}

/**
 * Data of the cell
 */
export interface CellData {
  id: CellId;
  /** user-given name, or default */
  name: string;
  /** current contents of the editor */
  code: string;
  /** whether this cell has been modified since its last run */
  edited: boolean;
  /** snapshot of code that was last run */
  lastCodeRun: string | null;
  /** execution time on session start / resume */
  lastExecutionTime: number | null;
  /** cell configuration */
  config: CellConfig;
}

export interface CellRuntimeState {
  /** a message encoding the cell's output */
  output: OutputMessage | null;
  /** TOC outline */
  outline: Outline | null;
  /** messages encoding the cell's console outputs. */
  consoleOutputs: ConsoleOutputMessage[];
  /** current status of the cell */
  status: RuntimeState;
  /** whether the cell has stale inputs*/
  staleInputs: boolean;
  /** whether this cell has been interrupted since its last run */
  interrupted: boolean;
  /** whether this cell was stopped with mo.stop */
  stopped: boolean;
  /**
   * whether marimo encountered an error when trying to register or run
   * this cell (such as a multiple definition error)
   */
  errored: boolean;
  /** run start time, as seconds since epoch */
  runStartTimestamp: Seconds | null;
  /** run elapsed time, in milliseconds */
  runElapsedTimeMs: Milliseconds | null;
  /** last run timestamp, as seconds since epoch */
  lastRunStartTimestamp: Seconds | null;
  /** debugger active */
  debuggerActive: boolean;
  /** serialization message */
  serialization?: string | null;
}

export type RuntimeCell = CellRuntimeState & CellData;

export type WithResponse<T> = T & {
  /**
   * This is not saved to the server, but we update this field
   * after sending the message to the kernel.
   */
  response?: string;
};

/**
 * A console output as held by the frontend. The id is assigned when the
 * output arrives and never changes, so it can identify the output while
 * neighboring outputs collapse, truncate, or receive a stdin response.
 */
export type ConsoleOutputMessage = WithResponse<OutputMessage> & {
  id?: number;
};
