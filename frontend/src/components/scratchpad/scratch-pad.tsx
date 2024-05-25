/* Copyright 2024 Marimo. All rights reserved. */
import type React from "react";
import {
  LastSavedNotebook,
  flattenNotebookCells,
  useCellActions,
  useNotebook,
} from "@/core/cells/cells";
import {
  getAppConfig,
  getUserConfig,
  useUserConfig,
} from "@/core/config/config";
import { useState } from "react";
import { useAtom } from "jotai";
import { viewStateAtom } from "@/core/mode";
import { useTheme } from "@/theme/useTheme";
import { Cell } from "../editor/Cell";
import { CellId } from "@/core/cells/ids";
export const ScratchPad: React.FC = () => {
  const notebook = useNotebook();
  const [lastSavedNotebook, setLastSavedNotebook] =
    useState<LastSavedNotebook>();
  const [viewState, setViewState] = useAtom(viewStateAtom);
  const { theme } = useTheme();

  const {
    updateCellCode,
    prepareForRun,
    moveCell,
    moveToNextCell,
    updateCellConfig,
    clearSerializedEditorState,
    focusCell,
    createNewCell,
    focusBottomCell,
    focusTopCell,
    scrollToTarget,
    foldAll,
    unfoldAll,
    sendToBottom,
    sendToTop,
    setStdinResponse,
  } = useCellActions();
  const cells = flattenNotebookCells(notebook);
  const testCell = cells[0];
  return (
    <div className="p-2">
      <Cell
        key={"scratch"}
        theme={theme}
        showPlaceholder={false}
        allowFocus={true}
        id={cells[0].id}
        code={testCell.code}
        output={testCell.output}
        consoleOutputs={testCell.consoleOutputs}
        status={testCell.status}
        updateCellCode={updateCellCode}
        prepareForRun={prepareForRun}
        edited={testCell.edited}
        interrupted={testCell.interrupted}
        errored={testCell.errored}
        stopped={testCell.stopped}
        staleInputs={testCell.staleInputs}
        runStartTimestamp={testCell.runStartTimestamp}
        runElapsedTimeMs={testCell.runElapsedTimeMs}
        serializedEditorState={testCell.serializedEditorState}
        showDeleteButton={cells.length > 1 && !testCell.config.hide_code}
        createNewCell={createNewCell}
        deleteCell={console.log}
        focusCell={focusCell}
        moveToNextCell={moveToNextCell}
        setStdinResponse={setStdinResponse}
        updateCellConfig={updateCellConfig}
        clearSerializedEditorState={clearSerializedEditorState}
        moveCell={moveCell}
        mode={"edit"}
        appClosed={false}
        ref={notebook.cellHandles[testCell.id]}
        sendToBottom={sendToBottom}
        sendToTop={sendToTop}
        userConfig={getUserConfig()}
        debuggerActive={testCell.debuggerActive}
        config={testCell.config}
        name={testCell.name}
        isScratchpad={true}
      />
    </div>
  );
};
