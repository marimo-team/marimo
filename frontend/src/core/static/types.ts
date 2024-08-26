/* Copyright 2024 Marimo. All rights reserved. */
import type {
  Base64String,
  DataURLString,
  JsonString,
} from "@/utils/json/base64";
import type { CellId } from "../cells/ids";
import type { OutputMessage } from "../kernel/messages";
import type { CellConfig } from "../network/types";

export interface StaticNotebookState {
  cellIds: CellId[];
  cellNames: Array<Base64String<string>>;
  cellCodes: Array<Base64String<string>>;
  cellConfigs: Array<Base64String<JsonString<CellConfig>>>;
  /**
   * The runtime output of each cell.
   * {
   *  "cell-1": "base64 json string",
   * }
   */
  cellOutputs: Record<
    CellId,
    Base64String<JsonString<OutputMessage>> | undefined
  >;
  /**
   * The data of each cell.
   *
   */
  cellConsoleOutputs: Record<
    CellId,
    Array<Base64String<JsonString<OutputMessage>>> | undefined
  >;
}

export type StaticVirtualFiles = Record<string, DataURLString>;

export interface MarimoStaticState {
  version: string;
  notebookState: StaticNotebookState;
  assetUrl: string;
  files: StaticVirtualFiles;
}
