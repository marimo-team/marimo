/* Copyright 2024 Marimo. All rights reserved. */
import type React from "react";
import { useUserConfig } from "@/core/config/config";
import { useRef } from "react";
import { useTheme } from "@/theme/useTheme";
import { CellEditor } from "../editor/cell/code/cell-editor";
import { HTMLCellId } from "@/core/cells/ids";
import { Functions } from "@/utils/functions";
import type { EditorView } from "@codemirror/view";
import useEvent from "react-use-event-hook";
import { sendRunScratchpad } from "@/core/network/requests";
import { OutputArea } from "../editor/Output";
import { ConsoleOutput } from "../editor/output/ConsoleOutput";
import {
  SCRATCH_CELL_ID,
  useCellActions,
  useNotebook,
} from "@/core/cells/cells";
import { DEFAULT_CELL_NAME } from "@/core/cells/names";
import { Button } from "../ui/button";
import { Tooltip } from "../ui/tooltip";
import { renderShortcut } from "../shortcuts/renderShortcut";
import { BetweenHorizontalStartIcon, EraserIcon, PlayIcon } from "lucide-react";
import { HideInKioskMode } from "../editor/kiosk-mode";
import { useLastFocusedCellId } from "@/core/cells/focus";
import { Spinner } from "../icons/spinner";

export const ScratchPad: React.FC = () => {
  const notebookState = useNotebook();
  const [userConfig] = useUserConfig();
  const { theme } = useTheme();
  const ref = useRef<EditorView>(null);
  const lastFocusedCellId = useLastFocusedCellId();
  const { createNewCell, updateCellCode } = useCellActions();

  const cellId = SCRATCH_CELL_ID;
  const cellRuntime = notebookState.cellRuntime[cellId];
  const output = cellRuntime?.output;
  const status = cellRuntime?.status;
  const consoleOutputs = cellRuntime?.consoleOutputs;
  const cellData = notebookState.cellData[cellId];
  const code = cellData?.code ?? "";

  const handleRun = useEvent(() => {
    sendRunScratchpad({ code });
  });

  const handleInsertCode = useEvent(() => {
    if (!code.trim()) {
      return;
    }
    createNewCell({
      code,
      before: false,
      cellId: lastFocusedCellId ?? "__end__",
    });
  });

  const handleClearCode = useEvent(() => {
    updateCellCode({
      cellId,
      code: "",
      formattingChange: false,
    });
    sendRunScratchpad({ code: "" });
    const ev = ref.current;
    if (ev) {
      ev.dispatch({
        changes: {
          from: 0,
          to: ev.state.doc.length,
          insert: "",
        },
      });
    }
  });

  return (
    <div
      className="flex flex-col h-full overflow-hidden divide-y"
      id={HTMLCellId.create(cellId)}
    >
      <div className="flex items-center flex-shrink-0">
        <Tooltip content={renderShortcut("cell.run")}>
          <Button
            data-testid="scratchpad-run-button"
            onClick={handleRun}
            variant="text"
            // className="bg-[var(--grass-3)] hover:bg-[var(--grass-4)] rounded-none"
            size="xs"
          >
            <PlayIcon color="var(--grass-11)" size={16} />
          </Button>
        </Tooltip>
        <Tooltip content="Clear code and outputs">
          <Button size="xs" variant="text" onClick={handleClearCode}>
            <EraserIcon size={16} />
          </Button>
        </Tooltip>
        <HideInKioskMode>
          <Tooltip content="Insert code">
            <Button size="xs" variant="text" onClick={handleInsertCode}>
              <BetweenHorizontalStartIcon size={16} />
            </Button>
          </Tooltip>
        </HideInKioskMode>
        {(status === "running" || status === "queued") && (
          <Spinner className="inline" size="small" />
        )}
      </div>
      <div className="overflow-auto flex-shrink-0 max-h-[40%]">
        <CellEditor
          theme={theme}
          allowFocus={false}
          showPlaceholder={false}
          id={cellId}
          code={code}
          status="idle"
          serializedEditorState={null}
          runCell={handleRun}
          updateCellCode={updateCellCode}
          createNewCell={Functions.NOOP}
          deleteCell={Functions.NOOP}
          focusCell={Functions.NOOP}
          moveCell={Functions.NOOP}
          moveToNextCell={undefined}
          updateCellConfig={Functions.NOOP}
          clearSerializedEditorState={Functions.NOOP}
          userConfig={userConfig}
          editorViewRef={ref}
          hidden={false}
        />
      </div>
      <div className="flex-1 overflow-auto flex-shrink-0">
        <OutputArea
          allowExpand={false}
          output={output}
          className="output-area"
          cellId={cellId}
          stale={false}
        />
      </div>
      <div className="overflow-auto flex-shrink-0 max-h-[35%]">
        <ConsoleOutput
          consoleOutputs={consoleOutputs}
          className="overflow-auto"
          stale={false}
          cellName={DEFAULT_CELL_NAME}
          onSubmitDebugger={Functions.NOOP}
          cellId={cellId}
          debuggerActive={false}
        />
      </div>
    </div>
  );
};
