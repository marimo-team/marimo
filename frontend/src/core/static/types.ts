/* Copyright 2023 Marimo. All rights reserved. */
import { NotebookState } from "../cells/cells";

export interface StaticNotebookState
  extends Pick<NotebookState, "cellIds" | "cellData" | "cellRuntime"> {
  version: string;
  assetUrl: string;
}

export type StaticVirtualFiles = Record<string, { base64: string }>;

export interface MarimoStaticState {
  version: string;
  notebookState: StaticNotebookState;
  assetUrl: string;
  files: StaticVirtualFiles;
}
