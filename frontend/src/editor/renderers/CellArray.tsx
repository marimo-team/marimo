/* Copyright 2023 Marimo. All rights reserved. */
import { useEffect } from "react";
import { EditorView } from "@codemirror/view";
import { sendDeleteCell } from "@/core/network/requests";
import { Cell } from "editor/Cell";
import { RuntimeState } from "../../core/RuntimeState";
import { ConnectionStatus, WebSocketState } from "../../core/websocket/types";
import { CellsAndHistory, useCellActions } from "../../core/state/cells";
import { AppConfig, UserConfig } from "../../core/config/config";
import { AppMode } from "../../core/mode";
import { useHotkey } from "../../hooks/useHotkey";
import { useEvent } from "../../hooks/useEvent";
import { CellId } from "../../core/model/ids";
import { formatEditorViews } from "../../core/codemirror/format";
import { useTheme } from "../../theme/useTheme";
import { VerticalLayoutWrapper } from "./vertical-layout/vertical-layout-wrapper";
import { useDelayVisibility } from "./vertical-layout/useDelayVisiblity";
import { useChromeActions } from "../chrome/state";

interface CellArrayProps {
  cells: CellsAndHistory;
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
  cells,
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

  const { invisible } = useDelayVisibility(cells.present);

  // HOTKEYS
  useHotkey("global.focusTop", focusTopCell);
  useHotkey("global.focusBottom", focusBottomCell);
  useHotkey("global.toggleSidebar", togglePanel);
  useHotkey("global.foldCode", foldAll);
  useHotkey("global.unfoldCode", unfoldAll);
  useHotkey("global.formatAll", () => {
    const views: Record<CellId, EditorView> = {};
    cells.present.forEach((cell) => {
      const editorView = cell.ref.current?.editorView;
      if (editorView) {
        views[cell.key] = editorView;
      }
    });
    formatEditorViews(views, updateCellCode);
  });

  const onDeleteCell: typeof deleteCell = useEvent((payload) => {
    sendDeleteCell(payload.cellId);
    deleteCell(payload);
  });

  // Scroll to a cell targeted by a previous action
  useEffect(() => {
    if (cells.scrollKey !== null) {
      scrollToTarget();
    }
  }, [cells.present, cells.scrollKey, scrollToTarget]);

  return (
    <VerticalLayoutWrapper invisible={invisible} appConfig={appConfig}>
      {cells.present.map((cell) => (
        <Cell
          key={cell.key.toString()}
          theme={theme}
          showPlaceholder={cells.present.length === 1}
          allowFocus={!invisible}
          cellId={cell.key}
          initialContents={cell.initialContents}
          output={cell.output}
          consoleOutputs={cell.consoleOutputs}
          status={cell.status}
          updateCellCode={updateCellCode}
          prepareForRun={prepareForRun}
          edited={cell.edited}
          interrupted={cell.interrupted}
          errored={cell.errored}
          stopped={cell.stopped}
          runElapsedTimeMs={cell.runElapsedTimeMs}
          registerRunStart={registerRunStart}
          serializedEditorState={cell.serializedEditorState}
          showDeleteButton={cells.present.length > 1}
          createNewCell={createNewCell}
          deleteCell={onDeleteCell}
          focusCell={focusCell}
          moveToNextCell={moveToNextCell}
          moveCell={moveCell}
          editing={mode === "edit"}
          appClosed={connStatus.state !== WebSocketState.OPEN}
          ref={cell.ref}
          userConfig={userConfig}
          config={cell.config}
        />
      ))}
    </VerticalLayoutWrapper>
  );
};
