/* Copyright 2026 Marimo. All rights reserved. */
import type { LayoutType } from "@/components/editor/renderers/types";
import { Logger } from "@/utils/Logger";
import { Objects } from "@/utils/objects";
import type { UIElementId } from "../cells/ids";
import type { ReducerCellActions } from "../cells/cells";
import type { CellData } from "../cells/types";
import { type AppConfig, AppConfigSchema } from "../config/config-schema";
import { UI_ELEMENT_REGISTRY } from "../dom/uiregistry";
import { deserializeLayoutState } from "../layout/layout";
import type { LayoutData, LayoutState } from "../layout/state";
import { getRequestClient } from "../network/requests";
import { VirtualFileTracker } from "../static/virtual-file-tracker";
import type {
  Capabilities,
  CellMessage,
  NotificationMessageData,
} from "./messages";
import type { KernelState } from "./state";

type KernelReadyData = NotificationMessageData<"kernel-ready">;

/**
 * Build layout state from kernel-ready data.
 */
export function buildLayoutState(
  data: KernelReadyData,
  cells: CellData[],
  setLayoutData: (payload: {
    layoutView: LayoutType;
    data: LayoutData;
  }) => void,
): LayoutState {
  const { layout } = data;
  const layoutState = deserializeLayoutState(layout, cells);

  if (layout && layout.type === layoutState.selectedLayout) {
    setLayoutData({
      layoutView: layoutState.selectedLayout,
      data: layoutState.layoutData[layoutState.selectedLayout],
    });
  }

  return layoutState;
}

/**
 * Collect current UI element values from the registry.
 */
function collectUIElementValues() {
  const objectIds: UIElementId[] = [];
  const values: unknown[] = [];
  UI_ELEMENT_REGISTRY.entries.forEach((entry, objectId) => {
    objectIds.push(objectId);
    values.push(entry.value);
  });
  return { objectIds, values };
}

export function handleKernelReady(
  data: KernelReadyData,
  opts: {
    autoInstantiate: boolean;
    /** The notebook's cells, as the host document provided them. */
    cells: CellData[];
    setLastRun: ReducerCellActions["setLastRun"];
    resetCellRuntimes: ReducerCellActions["resetCellRuntimes"];
    setLayoutData: (payload: {
      layoutView: LayoutType;
      data: LayoutData;
    }) => void;
    setCapabilities: (capabilities: Capabilities) => void;
    setKernelState: (state: KernelState) => void;
    setAppConfig: (config: AppConfig) => void;
    onError: (error: Error) => void;
  },
): LayoutState {
  const {
    autoInstantiate,
    cells,
    setLastRun,
    resetCellRuntimes,
    setLayoutData,
    setAppConfig,
    setCapabilities,
    setKernelState,
    onError,
  } = opts;
  const { resumed, ui_values, app_config, capabilities, auto_instantiated } =
    data;

  resetCellRuntimes();
  setLastRun({
    lastCodeRun: data.last_executed_code ?? {},
    lastExecutionTime: data.last_execution_time ?? {},
  });
  const layoutState = buildLayoutState(data, cells, setLayoutData);

  // Set app config and capabilities
  const parsedAppConfig = AppConfigSchema.safeParse(app_config);
  if (parsedAppConfig.success) {
    setAppConfig(parsedAppConfig.data);
  } else {
    Logger.error("Failed to parse app config", parsedAppConfig.error);
  }
  setCapabilities(capabilities);

  // If the kernel was already instantiated server-side (e.g. run mode), we're done
  if (auto_instantiated) {
    return layoutState;
  }

  // If resumed, restore UI element values from kernel and we're done
  if (resumed) {
    for (const [objectId, value] of Objects.entries(ui_values || {})) {
      // @ts-expect-error - TODO: We need to fix the types for KernelReadyNotification["ui_values"]
      // It is currently typed as Record<string, any> and should be Record<UIElementId, unknown>
      const uiObjectId: UIElementId = objectId;
      UI_ELEMENT_REGISTRY.set(uiObjectId, value);
    }
    return layoutState;
  }

  // If we already have values for some objects, we should
  // send them to the kernel. This may happen after re-connecting
  // to the kernel after the computer wakes from sleep.
  const { objectIds, values } = collectUIElementValues();

  // Send instantiate request to kernel
  void getRequestClient()
    .sendInstantiate({
      objectIds,
      values,
      autoRun: autoInstantiate,
    })
    .then(() => {
      setKernelState({ isInstantiated: true, error: null });
    })
    .catch((error) => {
      setKernelState({ isInstantiated: false, error: error });
      onError(new Error("Failed to instantiate", { cause: error }));
    });
  return layoutState;
}

export function handleRemoveUIElements(
  data: NotificationMessageData<"remove-ui-elements">,
) {
  // This removes the element from the registry to (1) clean-up
  // memory and (2) make sure that the old value doesn't get re-used
  // if the same cell-id is later reused for another element.
  const cellId = data.cell_id;
  UI_ELEMENT_REGISTRY.removeElementsByCell(cellId);
  VirtualFileTracker.INSTANCE.removeForCellId(cellId);
}

export function handleCellNotificationeration(
  data: NotificationMessageData<"cell-op">,
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
