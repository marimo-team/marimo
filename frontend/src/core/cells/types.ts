/* Copyright 2024 Marimo. All rights reserved. */

import type { Milliseconds, Seconds } from "@/utils/time";
import type { SerializedEditorState } from "../codemirror/types";
import type { OutputMessage } from "../kernel/messages";
import type { CellConfig, RuntimeState } from "../network/types";
import type { CellId } from "./ids";
import { DEFAULT_CELL_NAME } from "./names";
import type { Outline } from "./outline";

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
  serializedEditorState = null,
}: Partial<CellData> & { id: CellId }): CellData {
  return {
    id: id,
    config: config || {
      hide_code: false,
      disabled: false,
      column: null,
    },
    name: name,
    code: code,
    edited: edited,
    lastCodeRun: lastCodeRun,
    lastExecutionTime: lastExecutionTime,
    serializedEditorState: serializedEditorState,
  };
}

export function createCellConfig(config?: Partial<CellConfig>): CellConfig {
  return {
    hide_code: false,
    disabled: false,
    column: null,
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
  /** serialized state of the underlying editor */
  serializedEditorState: SerializedEditorState | null;
}

export interface CellRuntimeState {
  /** a message encoding the cell's output */
  output: OutputMessage | null;
  /** TOC outline */
  outline: Outline | null;
  /** messages encoding the cell's console outputs. */
  consoleOutputs: Array<WithResponse<OutputMessage>>;
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

export type WithResponse<T> = T & {
  /**
   * This is not saved to the server, but we update this field
   * after sending the message to the kernel.
   */
  response?: string;
};
