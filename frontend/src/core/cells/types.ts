/* Copyright 2024 Marimo. All rights reserved. */
import { OutputMessage } from "../kernel/messages";
import { SerializedEditorState } from "../codemirror/types";
import { Outline } from "./outline";
import { CellId } from "./ids";
import { DEFAULT_CELL_NAME } from "./names";
import { Milliseconds, Seconds } from "@/utils/time";

/**
 * The status of a cell.
 *
 * queued: queued by the kernel.
 * running: currently executing.
 * idle: not running.
 * stale: stale, likely because the cell was disabled or an ancestor was disabled.
 * disabled-transitively: disabled because an ancestor was disabled.
 */
export type CellStatus =
  | "queued"
  | "running"
  | "idle"
  | "stale"
  | "disabled-transitively";

/**
 * Create a new cell with default state.
 */
export function createCell({
  id,
  name = DEFAULT_CELL_NAME,
  code = "",
  lastCodeRun = null,
  edited = false,
  config = {},
  serializedEditorState = null,
}: Partial<CellData> & { id: CellId }): CellData {
  return {
    id: id,
    config: config,
    name: name,
    code: code,
    edited: edited,
    lastCodeRun: lastCodeRun,
    serializedEditorState: serializedEditorState,
  };
}

export function createCellRuntimeState(): CellRuntimeState {
  return {
    outline: null,
    output: null,
    consoleOutputs: [],
    status: "idle",
    interrupted: false,
    errored: false,
    stopped: false,
    runElapsedTimeMs: null,
    runStartTimestamp: null,
    debuggerActive: false,
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
  /** serialized state of the underlying editor */
  serializedEditorState: SerializedEditorState | null;
}

export interface CellRuntimeState {
  /** a message encoding the cell's output */
  output: OutputMessage | null;
  /** TOC outline */
  outline: Outline | null;
  /** messages encoding the cell's console outputs. */
  consoleOutputs: OutputMessage[];
  /** current status of the cell */
  status: CellStatus;
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
  /** debugger active */
  debuggerActive: boolean;
}

export interface CellConfig {
  /**
   * If true, the cell and its descendants are unable to run.
   */
  disabled?: boolean;
  /**
   * If true, the cell's code is hidden from the notebook.
   */
  hide_code?: boolean;
}
