/* Copyright 2024 Marimo. All rights reserved. */
import { useEffect } from "react";
import { Cell } from "@/components/editor/Cell";
import {
  type ConnectionStatus,
  WebSocketState,
} from "../../../core/websocket/types";
import {
  type NotebookState,
  flattenNotebookCells,
  useCellActions,
} from "../../../core/cells/cells";
import type { AppConfig, UserConfig } from "../../../core/config/config-schema";
import type { AppMode } from "../../../core/mode";
import { useHotkey } from "../../../hooks/useHotkey";
import { formatAll } from "../../../core/codemirror/format";
import { useTheme } from "../../../theme/useTheme";
import { VerticalLayoutWrapper } from "./vertical-layout/vertical-layout-wrapper";
import { useDelayVisibility } from "./vertical-layout/useDelayVisibility";
import { useChromeActions } from "../chrome/state";
import { Functions } from "@/utils/functions";
import { NotebookBanner } from "../notebook-banner";
import { PackageAlert } from "@/components/editor/package-alert";
import { useDeleteCellCallback } from "../cell/useDeleteCell";
import { cn } from "@/utils/cn";
import { Button } from "@/components/ui/button";
import {
  DatabaseIcon,
  SparklesIcon,
  SquareCodeIcon,
  SquareMIcon,
} from "lucide-react";
import { maybeAddMarimoImport } from "@/core/cells/add-missing-import";
import { aiEnabledAtom, autoInstantiateAtom } from "@/core/config/config";
import { useAtomValue } from "jotai";
import { useBoolean } from "@/hooks/useBoolean";
import { AddCellWithAI } from "../ai/add-cell-with-ai";
import type { Milliseconds } from "@/utils/time";
import { SQLLanguageAdapter } from "@/core/codemirror/language/sql";
import { MarkdownLanguageAdapter } from "@/core/codemirror/language/markdown";
import { capabilitiesAtom } from "@/core/config/capabilities";
import { Tooltip } from "@/components/ui/tooltip";
import { Kbd } from "@/components/ui/kbd";
import { isWasm } from "@/core/wasm/utils";

interface CellArrayProps {
  notebook: NotebookState;
  mode: AppMode;
  userConfig: UserConfig;
  appConfig: AppConfig;
  connStatus: ConnectionStatus;
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
  const { theme } = useTheme();
  const { toggleSidebarPanel } = useChromeActions();

  const { invisible } = useDelayVisibility(notebook.cellIds.length, mode);

  // HOTKEYS
  useHotkey("global.focusTop", focusTopCell);
  useHotkey("global.focusBottom", focusBottomCell);
  useHotkey("global.toggleSidebar", toggleSidebarPanel);
  useHotkey("global.foldCode", foldAll);
  useHotkey("global.unfoldCode", unfoldAll);
  useHotkey("global.formatAll", () => {
    formatAll(updateCellCode);
  });
  // Catch all to avoid native OS behavior
  // Otherwise a user might try to hide a cell and accidentally hide the OS window
  useHotkey("cell.hideCode", Functions.NOOP);
  useHotkey("cell.format", Functions.NOOP);

  const onDeleteCell = useDeleteCellCallback();

  // Scroll to a cell targeted by a previous action
  useEffect(() => {
    if (notebook.scrollKey !== null) {
      scrollToTarget();
    }
  }, [notebook.cellIds, notebook.scrollKey, scrollToTarget]);

  const cells = flattenNotebookCells(notebook);

  return (
    <VerticalLayoutWrapper
      // 'pb' allows the user to put the cell in the middle of the screen
      className="pb-[40vh]"
      invisible={invisible}
      appConfig={appConfig}
    >
      <PackageAlert />
      <NotebookBanner />
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
          staleInputs={cell.staleInputs}
          runStartTimestamp={cell.runStartTimestamp}
          runElapsedTimeMs={
            cell.runElapsedTimeMs ?? (cell.lastExecutionTime as Milliseconds)
          }
          serializedEditorState={cell.serializedEditorState}
          showDeleteButton={cells.length > 1 && !cell.config.hide_code}
          createNewCell={createNewCell}
          deleteCell={onDeleteCell}
          focusCell={focusCell}
          moveToNextCell={moveToNextCell}
          setStdinResponse={setStdinResponse}
          updateCellConfig={updateCellConfig}
          clearSerializedEditorState={clearSerializedEditorState}
          moveCell={moveCell}
          mode={mode}
          appClosed={connStatus.state !== WebSocketState.OPEN}
          ref={notebook.cellHandles[cell.id]}
          sendToBottom={sendToBottom}
          sendToTop={sendToTop}
          userConfig={userConfig}
          debuggerActive={cell.debuggerActive}
          config={cell.config}
          name={cell.name}
        />
      ))}
      <AddCellButtons />
    </VerticalLayoutWrapper>
  );
};

const AddCellButtons: React.FC = () => {
  const { createNewCell } = useCellActions();
  const autoInstantiate = useAtomValue(autoInstantiateAtom);
  const [isAiButtonOpen, isAiButtonOpenActions] = useBoolean(false);
  const aiEnabled = useAtomValue(aiEnabledAtom);
  const sqlCapabilities = useAtomValue(capabilitiesAtom).sql;

  const buttonClass = cn(
    "mb-0 rounded-none sm:px-4 md:px-5 lg:px-8 tracking-wide no-wrap whitespace-nowrap",
    "hover:bg-accent hover:text-accent-foreground font-semibold uppercase text-xs",
  );

  const renderBody = () => {
    if (isAiButtonOpen) {
      return <AddCellWithAI onClose={isAiButtonOpenActions.toggle} />;
    }

    return (
      <>
        <Button
          className={buttonClass}
          variant="text"
          size="sm"
          onClick={() => createNewCell({ cellId: "__end__", before: false })}
        >
          <SquareCodeIcon className="mr-2 size-4 flex-shrink-0" />
          Code
        </Button>
        <Button
          className={buttonClass}
          variant="text"
          size="sm"
          onClick={() => {
            maybeAddMarimoImport(autoInstantiate, createNewCell);

            createNewCell({
              cellId: "__end__",
              before: false,
              code: new MarkdownLanguageAdapter().defaultCode,
            });
          }}
        >
          <SquareMIcon className="mr-2 size-4 flex-shrink-0" />
          Markdown
        </Button>
        {!isWasm() && (
          <Tooltip
            content={
              sqlCapabilities ? null : (
                <span>
                  Requires duckdb:{" "}
                  <Kbd className="inline">pip install duckdb</Kbd>
                </span>
              )
            }
            delayDuration={100}
            asChild={false}
          >
            <Button
              className={buttonClass}
              variant="text"
              size="sm"
              disabled={!sqlCapabilities}
              onClick={() => {
                maybeAddMarimoImport(autoInstantiate, createNewCell);

                createNewCell({
                  cellId: "__end__",
                  before: false,
                  code: new SQLLanguageAdapter().defaultCode,
                });
              }}
            >
              <DatabaseIcon className="mr-2 size-4 flex-shrink-0" />
              SQL
            </Button>
          </Tooltip>
        )}
        <Tooltip
          content={
            aiEnabled ? null : <span>Enable via settings under AI Assist</span>
          }
          delayDuration={100}
          asChild={false}
        >
          <Button
            className={buttonClass}
            variant="text"
            size="sm"
            disabled={!aiEnabled}
            onClick={isAiButtonOpenActions.toggle}
          >
            <SparklesIcon className="mr-2 size-4 flex-shrink-0" />
            Generate with AI
          </Button>
        </Tooltip>
      </>
    );
  };

  return (
    <div className="flex justify-center mt-4 pt-6 pb-32 group gap-4 w-full">
      <div
        className={cn(
          "shadow-sm border border-border rounded transition-all duration-200 overflow-hidden divide-x divide-border flex",
          !isAiButtonOpen && "opacity-0 group-hover:opacity-100 w-fit",
          isAiButtonOpen && "opacity-100 w-full max-w-4xl shadow-lg",
        )}
      >
        {renderBody()}
      </div>
    </div>
  );
};
