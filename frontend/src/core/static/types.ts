/* Copyright 2023 Marimo. All rights reserved. */
import { Base64String } from "@/utils/json/base64";
import { NotebookState } from "../cells/cells";
import { CellId } from "../cells/ids";

export interface StaticNotebookState extends Pick<NotebookState, "cellIds"> {
  version: string;
  assetUrl: string;
  cellRuntime: Record<CellId, Base64String>;
  cellData: Record<CellId, Base64String>;
}

export type StaticVirtualFiles = Record<string, { base64: Base64String }>;

export interface MarimoStaticState {
  version: string;
  notebookState: StaticNotebookState;
  assetUrl: string;
  files: StaticVirtualFiles;
}
