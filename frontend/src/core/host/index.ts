/* Copyright 2026 Marimo. All rights reserved. */

/** Notebook backends and the replica that follows them. */

export type { NotebookBackend } from "./backend";
export {
  type CloseDecision,
  ConnectionClosedReason,
  ConnectionState,
  type ConnectionStatus,
} from "./connection";
export { createNotebookReplica, type NotebookReplica } from "./replica";
export type { Document } from "./resources/document";
export { createWasmNotebookBackend } from "./wasm";
