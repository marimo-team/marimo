/* Copyright 2026 Marimo. All rights reserved. */

import type { OutputMessage } from "../kernel/messages";
import type { CellConfig } from "../network/types";
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
  /** cell configuration */
  config: CellConfig;
}

/**
 * What the kernel's cell-ops still own. Status, timing, and how a cell last
 * ended come from the host's executions (see `@/core/executions`).
 *
 * TODO(MO-8407): Delete.
 */
export interface CellRuntimeState {
  /** a message encoding the cell's output. TODO(MO-8404) */
  output: OutputMessage | null;
  /** TOC outline. TODO(MO-8404) */
  outline: Outline | null;
  /** messages encoding the cell's console outputs. TODO(MO-8405) */
  consoleOutputs: ConsoleOutputMessage[];
  /** debugger active */
  debuggerActive: boolean;
  /** serialization message. TODO(MO-8414) */
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
