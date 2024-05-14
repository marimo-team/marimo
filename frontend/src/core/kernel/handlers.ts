/* Copyright 2024 Marimo. All rights reserved. */
import { deserializeLayout } from "@/components/editor/renderers/plugins";
import { Objects } from "@/utils/objects";
import { UI_ELEMENT_REGISTRY } from "../dom/uiregistry";
import { LayoutData, LayoutState, initialLayoutState } from "../layout/layout";
import { sendInstantiate } from "../network/requests";
import { CellMessage, OperationMessage } from "./messages";
import { LayoutType } from "@/components/editor/renderers/types";
import { AppConfig } from "../config/config-schema";
import { CellData, createCell } from "../cells/types";
import { VirtualFileTracker } from "../static/virtual-file-tracker";

export type OperationMessageData<T extends OperationMessage["op"]> = Extract<
  OperationMessage,
  { op: T }
>;

export function handleKernelReady(
  data: OperationMessageData<"kernel-ready">["data"],
  opts: {
    autoInstantiate: boolean;
    setCells: (cells: CellData[], layout: LayoutState) => void;
    setLayoutData: (payload: {
      layoutView: LayoutType;
      data: LayoutData;
    }) => void;
    setAppConfig: (config: AppConfig) => void;
    onError: (error: Error) => void;
  },
) {
  const { autoInstantiate, setCells, setLayoutData, onError, setAppConfig } =
    opts;

  const {
    codes,
    names,
    layout,
    configs,
    resumed,
    ui_values,
    cell_ids,
    last_executed_code = {},
    app_config,
  } = data;

  // Set the layout, initial codes, cells
  const cells = codes.map((code, i) => {
    const cellId = cell_ids[i];

    // A cell is stale if we did not auto-instantiate (i.e. nothing has run yet)
    // or if the code has changed since the last time it was run.
    let edited = false;
    if (autoInstantiate || resumed) {
      const lastCodeRun = last_executed_code[cellId];
      if (lastCodeRun) {
        edited = lastCodeRun !== code;
      }
    } else {
      edited = true;
    }

    return createCell({
      id: cellId,
      code,
      edited: edited,
      name: names[i],
      lastCodeRun: last_executed_code[cellId] ?? null,
      config: configs[i],
    });
  });

  const layoutState = initialLayoutState();
  if (layout) {
    const layoutData = deserializeLayout(layout.type, layout.data, cells);
    layoutState.selectedLayout = layout.type;
    layoutState.layoutData[layout.type] = layoutData;
    setLayoutData({ layoutView: layout.type, data: layoutData });
  }
  setCells(cells, layoutState);
  setAppConfig(app_config);

  // If resumed, we don't need to instantiate the UI elements,
  // and we should read in th existing values from the kernel.
  if (resumed) {
    for (const [objectId, value] of Objects.entries(ui_values || {})) {
      UI_ELEMENT_REGISTRY.set(objectId, value);
    }
    return;
  }

  // Auto-instantiate, in future this can be configurable
  // or include initial values
  const objectIds: string[] = [];
  const values: unknown[] = [];
  // If we already have values for some objects, we should
  // send them to the kernel. This may happen after re-connecting
  // to the kernel after the computer wakes from sleep.
  UI_ELEMENT_REGISTRY.entries.forEach((entry, objectId) => {
    objectIds.push(objectId);
    values.push(entry.value);
  });
  // Send the instantiate message
  if (autoInstantiate) {
    // Start the run
    sendInstantiate({ objectIds, values }).catch((error) => {
      onError(new Error("Failed to instantiate", { cause: error }));
    });
  }
}

export function handleRemoveUIElements(
  data: OperationMessageData<"remove-ui-elements">["data"],
) {
  // This removes the element from the registry to (1) clean-up
  // memory and (2) make sure that the old value doesn't get re-used
  // if the same cell-id is later reused for another element.
  const { cell_id } = data;
  UI_ELEMENT_REGISTRY.removeElementsByCell(cell_id);
  VirtualFileTracker.INSTANCE.removeForCellId(cell_id);
}

export function handleCellOperation(
  data: OperationMessageData<"cell-op">["data"],
  handleCellMessage: (message: CellMessage) => void,
) {
  /* Register a state transition for a cell.
   *
   * The cell may have a new output, a new console output,
   * it may have been queued, it may have started running, or
   * it may have stopped running. Each of these things
   * affects how the cell should be rendered.
   */
  handleCellMessage(data);
  VirtualFileTracker.INSTANCE.track(data);
}
