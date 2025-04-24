/* Copyright 2024 Marimo. All rights reserved. */
import type React from "react";
import { useResolvedMarimoConfig } from "@/core/config/config";
import { useRef, useState } from "react";
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
import {
  BetweenHorizontalStartIcon,
  EraserIcon,
  PlayIcon,
  HistoryIcon,
} from "lucide-react";
import { HideInKioskMode } from "../editor/kiosk-mode";
import { useLastFocusedCellId } from "@/core/cells/focus";
import { Spinner } from "../icons/spinner";
import { useAtom, useAtomValue, useSetAtom } from "jotai";
import {
  addToHistoryAtom,
  scratchpadHistoryAtom,
  historyVisibleAtom,
} from "./scratchpad-history";
import { cn } from "@/utils/cn";
import type { CellConfig } from "@/core/network/types";
import { LazyAnyLanguageCodeMirror } from "@/plugins/impl/code/LazyAnyLanguageCodeMirror";
import type { LanguageAdapterType } from "@/core/codemirror/language/types";

const scratchpadCellConfig: CellConfig = {
  hide_code: false,
  disabled: false,
};

export const ScratchPad: React.FC = () => {
  const notebookState = useNotebook();
  const [userConfig] = useResolvedMarimoConfig();
  const { theme } = useTheme();
  const ref = useRef<EditorView | null>(null);
  const lastFocusedCellId = useLastFocusedCellId();
  const { createNewCell, updateCellCode } = useCellActions();

  const cellId = SCRATCH_CELL_ID;
  const cellRuntime = notebookState.cellRuntime[cellId];
  const output = cellRuntime?.output;
  const status = cellRuntime?.status;
  const consoleOutputs = cellRuntime?.consoleOutputs;
  const cellData = notebookState.cellData[cellId];
  const code = cellData?.code ?? "";

  const addToHistory = useSetAtom(addToHistoryAtom);
  const [historyVisible, setHistoryVisible] = useAtom(historyVisibleAtom);
  const history = useAtomValue(scratchpadHistoryAtom);

  const handleRun = useEvent(() => {
    sendRunScratchpad({ code });
    addToHistory(code);
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

  const handleSelectHistoryItem = useEvent((item: string) => {
    setHistoryVisible(false);
    updateCellCode({
      cellId,
      code: item,
      formattingChange: false,
    });
    const ev = ref.current;
    if (ev) {
      ev.dispatch({
        changes: {
          from: 0,
          to: ev.state.doc.length,
          insert: item,
        },
      });
    }
  });

  const [languageAdapter, setLanguageAdapter] = useState<LanguageAdapterType>();

  const renderBody = () => {
    // We overlay the history on top of the body, instead of removing it,
    // so we don't have to re-render the entire editor and outputs.
    return (
      <>
        <div className="overflow-auto flex-shrink-0 max-h-[40%]">
          <CellEditor
            theme={theme}
            allowFocus={false}
            showPlaceholder={false}
            id={cellId}
            code={code}
            config={scratchpadCellConfig}
            status="idle"
            serializedEditorState={null}
            runCell={handleRun}
            userConfig={userConfig}
            editorViewRef={ref}
            setEditorView={(ev) => {
              ref.current = ev;
            }}
            hidden={false}
            temporarilyShowCode={Functions.NOOP}
            languageAdapter={languageAdapter}
            setLanguageAdapter={setLanguageAdapter}
          />
        </div>
        <div className="flex-1 overflow-auto flex-shrink-0">
          <OutputArea
            allowExpand={false}
            output={output}
            className="output-area"
            cellId={cellId}
            stale={false}
            loading={false}
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
      </>
    );
  };

  const renderHistory = () => {
    if (!historyVisible) {
      return null;
    }
    return (
      <div className="absolute inset-0 z-100 bg-background p-3 border-none overflow-auto">
        <div className="overflow-auto flex flex-col gap-3">
          {history.map((item, index) => (
            <div
              key={index}
              className="border rounded-md hover:shadow-sm cursor-pointer hover:border-input overflow-hidden"
              onClick={() => handleSelectHistoryItem(item)}
            >
              <LazyAnyLanguageCodeMirror
                language="python"
                theme={theme}
                basicSetup={{
                  highlightActiveLine: false,
                  highlightActiveLineGutter: false,
                }}
                value={item.trim()}
                editable={false}
                readOnly={true}
              />
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div
      className="flex flex-col h-full overflow-hidden divide-y"
      id={HTMLCellId.create(cellId)}
    >
      <p className="mx-2 my-2 text-muted-foreground text-sm">
        Use this scratchpad cell to experiment with throwaway code. Scratchpad
        code can redefine variables from the notebook; its variables aren't
        saved to notebook memory.
      </p>
      <div className="flex items-center flex-shrink-0">
        <Tooltip content={renderShortcut("cell.run")}>
          <Button
            data-testid="scratchpad-run-button"
            onClick={handleRun}
            disabled={historyVisible}
            variant="text"
            // className="bg-[var(--grass-3)] hover:bg-[var(--grass-4)] rounded-none"
            size="xs"
          >
            <PlayIcon color="var(--grass-11)" size={16} />
          </Button>
        </Tooltip>
        <Tooltip content="Clear code and outputs">
          <Button
            disabled={historyVisible}
            size="xs"
            variant="text"
            onClick={handleClearCode}
          >
            <EraserIcon size={16} />
          </Button>
        </Tooltip>
        <HideInKioskMode>
          <Tooltip content="Insert code">
            <Button
              disabled={historyVisible}
              size="xs"
              variant="text"
              onClick={handleInsertCode}
            >
              <BetweenHorizontalStartIcon size={16} />
            </Button>
          </Tooltip>
        </HideInKioskMode>

        {(status === "running" || status === "queued") && (
          <Spinner className="inline" size="small" />
        )}
        <div className="flex-1" />

        <Tooltip content="Toggle history">
          <Button
            size="xs"
            variant="text"
            className={cn(historyVisible && "bg-[var(--sky-3)] rounded-none")}
            onClick={() => setHistoryVisible(!historyVisible)}
            disabled={history.length === 0}
          >
            <HistoryIcon size={16} />
          </Button>
        </Tooltip>
      </div>
      <div className="flex-1 divide-y relative overflow-hidden flex flex-col">
        {renderBody()}
        {renderHistory()}
      </div>
    </div>
  );
};
