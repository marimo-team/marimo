/* Copyright 2026 Marimo. All rights reserved. */
import type { LayoutType } from "@/components/editor/renderers/types";
import { Objects } from "@/utils/objects";
import type { UIElementId } from "../cells/ids";
import type { ReducerCellActions } from "../cells/cells";
import type { CellData } from "../cells/types";
import { UI_ELEMENT_REGISTRY } from "../dom/uiregistry";
import { deserializeLayoutState } from "../layout/layout";
import type { LayoutData, LayoutState } from "../layout/state";
import { VirtualFileTracker } from "../static/virtual-file-tracker";
import type {
  Capabilities,
  CellMessage,
  NotificationMessageData,
} from "./messages";

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

export function handleKernelReady(
  data: KernelReadyData,
  opts: {
    /** The notebook's cells, as the host document provided them. */
    cells: CellData[];
    resetCellRuntimes: ReducerCellActions["resetCellRuntimes"];
    setLayoutData: (payload: {
      layoutView: LayoutType;
      data: LayoutData;
    }) => void;
    setCapabilities: (capabilities: Capabilities) => void;
  },
): LayoutState {
  const { cells, resetCellRuntimes, setLayoutData, setCapabilities } = opts;
  const { resumed, ui_values, capabilities, auto_instantiated } = data;

  resetCellRuntimes();
  const layoutState = buildLayoutState(data, cells, setLayoutData);

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
