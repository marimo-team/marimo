/* Copyright 2026 Marimo. All rights reserved. */

/** Backend-confirmed notebook state, independent of React and transports. */

export type { NotebookBackend } from "./backend";
export {
  type CloseDecision,
  ConnectionClosedReason,
  ConnectionState,
  type ConnectionStatus,
} from "./connection";
export { createNotebookReplica, type NotebookReplica } from "./replica";
export type { Document } from "./resources/document";
export {
  type Execution,
  type Executions,
  type Item,
  itemsInOrder,
} from "./resources/executions";
export type { Results } from "./resources/results";
