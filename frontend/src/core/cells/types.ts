/* Copyright 2026 Marimo. All rights reserved. */

import type { CellOutput } from "../executions";
import type { OutputMessage } from "../kernel/messages";
import type { CellConfig } from "../network/types";
import type { CommandConsole, CommandOutputMessage } from "./command-console";
import type { CellId } from "./ids";
import { DEFAULT_CELL_NAME } from "./names";

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
    embeddedConsole: [],
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

/** Console presentation and editor-session hints for a cell. */
export interface CellRuntimeState {
  /** Embedded console output until the notebook reports an execution. */
  embeddedConsole: ConsoleOutputMessage[];
  commandConsole?: CommandConsole;
  /** Last write hidden by this browser for each command transcript. */
  clearedCommandIds?: Partial<Record<CommandOutputMessage["op"], string>>;
  /** Settled input IDs hidden by this execution’s clear_console(). */
  clearedConsoleInputs?: { executionId: string; ids: ReadonlySet<string> };
  /** Only the browser that answered a prompt knows its non-secret reply. */
  answers?: ReadonlyMap<string, string>;
  /** Rows this browser hid, except prompts that were still pending. */
  clearedConsole?: {
    executionId: string;
    seq: number;
    prompts: ReadonlySet<string>;
  };
  /** serialization message. TODO(MO-8414) */
  serialization?: string | null;
}

/** The cell runtime fields available to renderers. */
export interface CellRuntimeView extends Pick<
  CellRuntimeState,
  "serialization"
> {
  consoleOutputs: ConsoleOutputMessage[];
}

/** A cell as the layout renderers take it, with what it shows from the host. */
export type RuntimeCell = CellData &
  CellRuntimeView & {
    output: CellOutput | null;
  };

export type WithResponse<T> = T & {
  /**
   * The locally accepted reply. Undefined means the prompt is pending.
   * Null closes the prompt when its answer is unavailable or secret.
   */
  response?: string | null;
};

/**
 * A console output as held by the frontend. The id is assigned when the
 * output arrives and never changes, so it can identify the output while
 * neighboring outputs collapse, truncate, or receive a stdin response.
 */
export type ConsoleOutputMessage = WithResponse<OutputMessage> & {
  id?: number;
};
