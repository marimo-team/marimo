/* Copyright 2023 Marimo. All rights reserved. */
import { createRef } from "react";
import { OutputMessage } from "../kernel/messages";
import { SerializedEditorState } from "../codemirror/types";
import { CellHandle } from "../../editor/Cell";
import { CellId } from "./ids";

export const DEFAULT_CELL_NAME = "__";

/**
 * The status of a cell.
 *
 * queued: queued by the kernel.
 * running: currently executing.
 * idle: not running.
 */
export type CellStatus = "queued" | "running" | "idle";

/**
 * Create a new cell with default state.
 */
export function createCell({
  key,
  ref = createRef(),
  name = DEFAULT_CELL_NAME,
  initialContents = "",
  code = "",
  output = null,
  consoleOutputs = [],
  status = "idle",
  edited = false,
  interrupted = false,
  errored = false,
  stopped = false,
  runElapsedTimeMs = null,
  runStartTimestamp = null,
  lastCodeRun = null,
  serializedEditorState = null,
  config = {},
}: Partial<CellState> & Pick<CellState, "key">): CellState {
  return {
    key: key,
    ref: ref,
    config: config,
    name: name,
    initialContents: initialContents,
    output: output,
    code: code,
    status: status,
    edited: edited,
    interrupted: interrupted,
    errored: errored,
    stopped: stopped,
    runElapsedTimeMs: runElapsedTimeMs,
    runStartTimestamp: runStartTimestamp,
    lastCodeRun: lastCodeRun,
    consoleOutputs: consoleOutputs,
    serializedEditorState: serializedEditorState,
  };
}

export interface CellState {
  /** unique key */
  key: CellId;
  /** user-given name, or default */
  name: string;
  /** initial contents of the editor */
  initialContents: string;
  /** current contents of the editor */
  code: string;
  /** a message encoding the cell's output */
  output: OutputMessage | null;
  /** messages encoding the cell's console outputs. */
  consoleOutputs: OutputMessage[];
  /** current status of the cell */
  status: CellStatus;
  /** whether this cell has been modified since its last run */
  edited: boolean;
  /** whether this cell has been interrupted since its last run */
  interrupted: boolean;
  /** whether this cell was stopped with mo.stop */
  stopped: boolean;
  /** snapshot of code that was last run */
  lastCodeRun: string | null;
  /**
   * whether marimo encountered an error when trying to register or run
   * this cell (such as a multiple definition error)
   */
  errored: boolean;
  /** run start time, as seconds since epoch */
  runStartTimestamp: number | null;
  /** run elapsed time, in milliseconds */
  runElapsedTimeMs: number | null;
  /** serialized state of the underyling editor */
  serializedEditorState: SerializedEditorState | null;

  /** handle to access the underlying cell */
  ref: React.RefObject<CellHandle>;

  /** cell configuration */
  config: CellConfig;
}

export interface CellConfig {
  /**
   * If false, the cell will not be run automatically.
   * Cannot be true, and instead will be set to null.
   */
  autoRun?: false | null;
}
