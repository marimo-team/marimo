/* Copyright 2024 Marimo. All rights reserved. */
import { useEffect } from "react";
import { Cell } from "@/components/editor/Cell";
import {
  type ConnectionStatus,
  WebSocketState,
} from "../../../core/websocket/types";
import { type NotebookState, useCellActions } from "../../../core/cells/cells";
import type { AppConfig, UserConfig } from "../../../core/config/config-schema";
import { viewStateAtom, type AppMode } from "../../../core/mode";
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
import { FloatingOutline } from "../chrome/panels/outline/floating-outline";
import {
  horizontalListSortingStrategy,
  SortableContext,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import {
  PlaceholderColumn,
  SortableCellsProvider,
} from "@/components/sort/SortableCellsProvider";
import type { CellColumnIndex } from "@/utils/id-tree";
import { Column } from "../Column";

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
  const actions = useCellActions();
  const { theme } = useTheme();
  const { toggleSidebarPanel } = useChromeActions();
  const viewState = useAtomValue(viewStateAtom);
  const isEditing = viewState.mode === "edit";

  const { invisible } = useDelayVisibility(
    notebook.cellIds.columns.length,
    mode,
  );

  // HOTKEYS
  useHotkey("global.focusTop", actions.focusTopCell);
  useHotkey("global.focusBottom", actions.focusBottomCell);
  useHotkey("global.toggleSidebar", toggleSidebarPanel);
  useHotkey("global.foldCode", actions.foldAll);
  useHotkey("global.unfoldCode", actions.unfoldAll);
  useHotkey("global.formatAll", () => {
    formatAll(actions.updateCellCode);
  });
  // Catch all to avoid native OS behavior
  // Otherwise a user might try to hide a cell and accidentally hide the OS window
  useHotkey("cell.hideCode", Functions.NOOP);
  useHotkey("cell.format", Functions.NOOP);

  const onDeleteCell = useDeleteCellCallback();

  // Scroll to a cell targeted by a previous action
  const scrollToTarget = actions.scrollToTarget;
  useEffect(() => {
    if (notebook.scrollKey !== null) {
      scrollToTarget();
    }
  }, [notebook.cellIds, notebook.scrollKey, scrollToTarget]);

  const columns = notebook.cellIds.columns;

  return (
    <VerticalLayoutWrapper
      // 'pb' allows the user to put the cell in the middle of the screen
      className="pb-[40vh]"
      invisible={invisible}
      appConfig={appConfig}
    >
      <PackageAlert />
      <NotebookBanner />
      <SortableCellsProvider>
        <SortableContext
          id="column-container"
          // First element of SortableContext cannot have id 0
          // https://stackoverflow.com/questions/73936273/
          items={columns.map((_, index) => (index + 1) as CellColumnIndex)}
          disabled={!isEditing}
          strategy={horizontalListSortingStrategy}
        >
          <div className="grid grid-flow-col auto-cols-min gap-28">
            {columns.map((column, index) => {
              return (
                <Column
                  key={(index + 1) as CellColumnIndex}
                  columnIndex={(index + 1) as CellColumnIndex}
                >
                  <SortableContext
                    id={`column-${index + 1}`}
                    items={column.topLevelIds}
                    disabled={!isEditing}
                    strategy={verticalListSortingStrategy}
                  >
                    {column.topLevelIds.map((cellId) => {
                      const cellData = notebook.cellData[cellId];
                      const cellRuntime = notebook.cellRuntime[cellId];
                      return (
                        <Cell
                          key={cellData.id.toString()}
                          theme={theme}
                          showPlaceholder={column.length === 1}
                          allowFocus={!invisible && !notebook.scrollKey}
                          id={cellData.id}
                          code={cellData.code}
                          outline={cellRuntime.outline}
                          output={cellRuntime.output}
                          consoleOutputs={cellRuntime.consoleOutputs}
                          status={cellRuntime.status}
                          edited={cellData.edited}
                          interrupted={cellRuntime.interrupted}
                          errored={cellRuntime.errored}
                          stopped={cellRuntime.stopped}
                          staleInputs={cellRuntime.staleInputs}
                          runStartTimestamp={cellRuntime.runStartTimestamp}
                          runElapsedTimeMs={
                            cellRuntime.runElapsedTimeMs ??
                            (cellData.lastExecutionTime as Milliseconds)
                          }
                          serializedEditorState={cellData.serializedEditorState}
                          showDeleteButton={
                            column.length > 1 && !cellData.config.hide_code
                          }
                          mode={mode}
                          appClosed={connStatus.state !== WebSocketState.OPEN}
                          ref={notebook.cellHandles[cellId]}
                          userConfig={userConfig}
                          debuggerActive={cellRuntime.debuggerActive}
                          config={cellData.config}
                          name={cellData.name}
                          isCollapsed={column.isCollapsed(cellId)}
                          collapseCount={column.getCount(cellId)}
                          canMoveX={appConfig.width === "columns"}
                          {...actions}
                          deleteCell={onDeleteCell}
                        />
                      );
                    })}
                    <AddCellButtons />
                  </SortableContext>
                </Column>
              );
            })}
            {appConfig.width === "columns" && (
              <div className="flex flex-col gap-5 w-[640px] max-w-[640px] min-w-[640px]">
                <PlaceholderColumn />
                <AddCellButtons />
              </div>
            )}
          </div>
        </SortableContext>
      </SortableCellsProvider>
      <FloatingOutline />
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
          Python
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
        <Tooltip
          content={
            sqlCapabilities ? null : (
              <div className="flex flex-col">
                <span>
                  Additional dependencies required:
                  <Kbd className="inline">pip install marimo[sql]</Kbd>.
                </span>
                <span>
                  You will need to restart the notebook after installing.
                </span>
              </div>
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
    <div className="flex justify-center mt-4 pt-6 pb-32 group gap-4 w-full print:hidden">
      <div
        className={cn(
          "shadow-sm border border-border rounded transition-all duration-200 overflow-hidden divide-x divide-border flex",
          !isAiButtonOpen && "w-fit",
          isAiButtonOpen &&
            "opacity-100 w-full max-w-4xl shadow-lg shadow-[var(--blue-3)]",
        )}
      >
        {renderBody()}
      </div>
    </div>
  );
};
