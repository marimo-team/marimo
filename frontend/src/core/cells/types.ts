/* Copyright 2026 Marimo. All rights reserved. */

import type { OutputMessage } from "../kernel/messages";
import type { CellConfig } from "../network/types";
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
    staleInputs: false,
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
  /** cell configuration */
  config: CellConfig;
}

/**
 * What the kernel's cell-ops still own. Status, timing, and how a cell last
 * ended come from the host's executions (see `@/core/executions`).
 */
export interface CellRuntimeState {
  /** a message encoding the cell's output */
  output: OutputMessage | null;
  /** TOC outline */
  outline: Outline | null;
  /** messages encoding the cell's console outputs. */
  consoleOutputs: ConsoleOutputMessage[];
  /** whether the cell has stale inputs*/
  staleInputs: boolean;
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
