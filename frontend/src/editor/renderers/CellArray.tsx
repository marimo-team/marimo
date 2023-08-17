/* Copyright 2023 Marimo. All rights reserved. */
import { EditorView } from "codemirror";
import { useEffect, useState } from "react";
import { sendDeleteCell } from "@/core/network/requests";
import { Cell } from "editor/Cell";
import { RuntimeState } from "../../core/RuntimeState";
import { ConnectionStatus, WebSocketState } from "../../core/websocket/types";
import { CellsAndHistory, useCellActions } from "../../core/state/cells";
import { AppConfig, UserConfig } from "../../core/config";
import { AppMode } from "../../core/mode";
import { useHotkey } from "../../hooks/useHotkey";
import { useEvent } from "../../hooks/useEvent";
import { CellId } from "../../core/model/ids";
import { formatEditorViews } from "../../core/codemirror/format";
import { cn } from "../../lib/utils";
import { useTheme } from "../../theme/useTheme";

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

  // Start the app as invisible and delay proportional to the number of cells,
  // to avoid most of the flickering when the app is loaded (b/c it is
  // streamed). Delaying also helps prevent cell editors from stealing focus.
  const [invisible, setInvisible] = useState(true);
  useEffect(() => {
    const delay = Math.max(Math.min((cells.present.length - 1) * 15, 100), 0);
    const timeout = setTimeout(() => {
      setInvisible(false);
      // Focus on the first cell if it's been mounted
      cells.present[0]?.ref.current?.editorView.focus();
    }, delay);
    return () => clearTimeout(timeout);
    // Delay only when app is first loaded
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // HOTKEYS
  useHotkey("global.focusTop", focusTopCell);
  useHotkey("global.focusBottom", focusBottomCell);
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

  const onDeleteCell = useEvent((cellId: CellId) => {
    sendDeleteCell(cellId);
    deleteCell(cellId);
  });

  // Scroll to a cell targeted by a previous action
  useEffect(() => {
    if (cells.scrollKey !== null) {
      scrollToTarget();
    }
  }, [cells.present, cells.scrollKey, scrollToTarget]);

  return (
    <div
      className={cn(
        "m-auto pb-12",
        appConfig.width === "full" && "px-24",
        appConfig.width !== "full" && "max-w-contentWidth",
        // Hide the cells for a fake loading effect, to avoid flickering
        invisible && "invisible"
      )}
    >
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
          prepareCellForRun={prepareForRun}
          edited={cell.edited}
          interrupted={cell.interrupted}
          errored={cell.errored}
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
        />
      ))}
    </div>
  );
};
