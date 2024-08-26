/* Copyright 2024 Marimo. All rights reserved. */
import { deserializeLayout } from "@/components/editor/renderers/plugins";
import { Objects } from "@/utils/objects";
import { UI_ELEMENT_REGISTRY } from "../dom/uiregistry";
import {
  type LayoutData,
  type LayoutState,
  initialLayoutState,
} from "../layout/layout";
import { sendInstantiate } from "../network/requests";
import type {
  Capabilities,
  CellMessage,
  OperationMessageData,
} from "./messages";
import type { LayoutType } from "@/components/editor/renderers/types";
import type { AppConfig } from "../config/config-schema";
import { type CellData, createCell } from "../cells/types";
import { VirtualFileTracker } from "../static/virtual-file-tracker";
import type { CellId, UIElementId } from "../cells/ids";
import { isWasm } from "../wasm/utils";

export function handleKernelReady(
  data: OperationMessageData<"kernel-ready">,
  opts: {
    autoInstantiate: boolean;
    setCells: (cells: CellData[], layout: LayoutState) => void;
    setLayoutData: (payload: {
      layoutView: LayoutType;
      data: LayoutData;
    }) => void;
    setCapabilities: (capabilities: Capabilities) => void;
    setAppConfig: (config: AppConfig) => void;
    onError: (error: Error) => void;
  },
) {
  const {
    autoInstantiate,
    setCells,
    setLayoutData,
    onError,
    setAppConfig,
    setCapabilities,
  } = opts;

  const {
    codes,
    names,
    layout,
    configs,
    resumed,
    ui_values,
    cell_ids,
    last_executed_code,
    last_execution_time = {},
    app_config,
    capabilities,
  } = data;
  const lastExecutedCode = last_executed_code || {};
  const lastExecutionTime = last_execution_time || {};

  // Set the layout, initial codes, cells
  const cells = codes.map((code, i) => {
    const cellId = cell_ids[i];

    // A cell is stale if we did not auto-instantiate (i.e. nothing has run yet)
    // or if the code has changed since the last time it was run.
    let edited = false;
    if (autoInstantiate || resumed) {
      const lastCodeRun = lastExecutedCode[cellId];
      if (lastCodeRun) {
        edited = lastCodeRun !== code;
      }
    } else {
      edited = true;
    }

    return createCell({
      id: cellId as CellId,
      code,
      edited: edited,
      name: names[i],
      lastCodeRun: lastExecutedCode[cellId] ?? null,
      lastExecutionTime: lastExecutionTime[cellId] ?? null,
      config: configs[i],
    });
  });

  const layoutState = initialLayoutState();
  if (layout) {
    const layoutType = layout.type as LayoutType;
    const layoutData = deserializeLayout(layoutType, layout.data, cells);
    layoutState.selectedLayout = layoutType;
    layoutState.layoutData[layoutType] = layoutData;
    setLayoutData({ layoutView: layoutType, data: layoutData });
  }
  setCells(cells, layoutState);
  setAppConfig({
    ...app_config,
  } as AppConfig);
  setCapabilities({
    ...capabilities,
    // always enable sql if wasm
    sql: capabilities.sql || isWasm(),
  });

  // If resumed, we don't need to instantiate the UI elements,
  // and we should read in th existing values from the kernel.
  if (resumed) {
    for (const [objectId, value] of Objects.entries(ui_values || {})) {
      UI_ELEMENT_REGISTRY.set(objectId as UIElementId, value);
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
    void sendInstantiate({ objectIds: objectIds, values }).catch((error) => {
      onError(new Error("Failed to instantiate", { cause: error }));
    });
  }
}

export function handleRemoveUIElements(
  data: OperationMessageData<"remove-ui-elements">,
) {
  // This removes the element from the registry to (1) clean-up
  // memory and (2) make sure that the old value doesn't get re-used
  // if the same cell-id is later reused for another element.
  const cell_id = data.cell_id as CellId;
  UI_ELEMENT_REGISTRY.removeElementsByCell(cell_id);
  VirtualFileTracker.INSTANCE.removeForCellId(cell_id);
}

export function handleCellOperation(
  data: OperationMessageData<"cell-op">,
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
