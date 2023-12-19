/* Copyright 2023 Marimo. All rights reserved. */
import { bind } from "valtio-yjs";
import { proxy } from "valtio";
import { ydoc } from "./provider";
import { NotebookState } from "../cells/cells";
import { CellId } from "../cells/ids";
import { CellData } from "../cells/types";

export function bindYDoc(state: NotebookState) {
  state.cellIds = proxy(state.cellIds);
  state.cellData = proxy(state.cellData);

  const cellIds = ydoc.getArray<CellId>("cellIds");
  bind(state.cellIds, cellIds);

  const cellData = ydoc.getMap<CellData>("cellData");
  bind(state.cellData, cellData);
}
