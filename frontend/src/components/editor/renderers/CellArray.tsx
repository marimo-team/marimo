/* Copyright 2023 Marimo. All rights reserved. */
import { useEffect } from "react";
import { sendDeleteCell } from "@/core/network/requests";
import { Cell } from "@/components/editor/Cell";
import { RuntimeState } from "../../../core/RuntimeState";
import {
  ConnectionStatus,
  WebSocketState,
} from "../../../core/websocket/types";
import {
  NotebookState,
  flattenNotebookCells,
  useCellActions,
} from "../../../core/cells/cells";
import { AppConfig, UserConfig } from "../../../core/config/config-schema";
import { AppMode } from "../../../core/mode";
import { useHotkey } from "../../../hooks/useHotkey";
import { useEvent } from "../../../hooks/useEvent";
import { formatAll } from "../../../core/codemirror/format";
import { useTheme } from "../../../theme/useTheme";
import { VerticalLayoutWrapper } from "./vertical-layout/vertical-layout-wrapper";
import { useDelayVisibility } from "./vertical-layout/useDelayVisiblity";
import { useChromeActions } from "../chrome/state";

interface CellArrayProps {
  notebook: NotebookState;
  mode: AppMode;
  userConfig: UserConfig;
  appConfig: AppConfig;
  connStatus: ConnectionStatus;
}

// TODO(akshayka): move running cells state machine to kernel
function registerRunStart() {
  RuntimeState.INSTANCE.registerRunStart();
}

export const CellArray: React.FC<CellArrayProps> = ({
  notebook,
  mode,
  userConfig,
  appConfig,
  connStatus,
}) => {
  const {
    updateCellCode,
    prepareForRun,
    deleteCell,
    moveCell,
    moveToNextCell,
    focusCell,
    createNewCell,
    focusBottomCell,
    focusTopCell,
    scrollToTarget,
    foldAll,
    unfoldAll,
  } = useCellActions();
  const { theme } = useTheme();
  const { togglePanel } = useChromeActions();

  const { invisible } = useDelayVisibility(notebook.cellIds.length, mode);

  // HOTKEYS
  useHotkey("global.focusTop", focusTopCell);
  useHotkey("global.focusBottom", focusBottomCell);
  useHotkey("global.toggleSidebar", togglePanel);
  useHotkey("global.foldCode", foldAll);
  useHotkey("global.unfoldCode", unfoldAll);
  useHotkey("global.formatAll", () => {
    formatAll(updateCellCode);
  });

  const onDeleteCell: typeof deleteCell = useEvent((payload) => {
    sendDeleteCell(payload.cellId);
    deleteCell(payload);
  });

  // Scroll to a cell targeted by a previous action
  useEffect(() => {
    if (notebook.scrollKey !== null) {
      scrollToTarget();
    }
  }, [notebook.cellIds, notebook.scrollKey, scrollToTarget]);

  const cells = flattenNotebookCells(notebook);

  return (
    <VerticalLayoutWrapper invisible={invisible} appConfig={appConfig}>
      {cells.map((cell) => (
        <Cell
          key={cell.id.toString()}
          theme={theme}
          showPlaceholder={cells.length === 1}
          allowFocus={!invisible}
          id={cell.id}
          code={cell.code}
          output={cell.output}
          consoleOutputs={cell.consoleOutputs}
          status={cell.status}
          updateCellCode={updateCellCode}
          prepareForRun={prepareForRun}
          edited={cell.edited}
          interrupted={cell.interrupted}
          errored={cell.errored}
          stopped={cell.stopped}
          runStartTimestamp={cell.runStartTimestamp}
          runElapsedTimeMs={cell.runElapsedTimeMs}
          registerRunStart={registerRunStart}
          serializedEditorState={cell.serializedEditorState}
          showDeleteButton={cells.length > 1}
          createNewCell={createNewCell}
          deleteCell={onDeleteCell}
          focusCell={focusCell}
          moveToNextCell={moveToNextCell}
          moveCell={moveCell}
          mode={mode}
          appClosed={connStatus.state !== WebSocketState.OPEN}
          ref={notebook.cellHandles[cell.id]}
          userConfig={userConfig}
          config={cell.config}
        />
      ))}
    </VerticalLayoutWrapper>
  );
};
