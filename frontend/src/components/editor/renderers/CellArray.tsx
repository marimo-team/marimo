/* Copyright 2024 Marimo. All rights reserved. */

import {
  horizontalListSortingStrategy,
  SortableContext,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { useAtomValue } from "jotai";
import {
  DatabaseIcon,
  SparklesIcon,
  SquareCodeIcon,
  SquareMIcon,
} from "lucide-react";
import { useEffect } from "react";
import { StartupLogsAlert } from "@/components/editor/alerts/startup-logs-alert";
import { Cell } from "@/components/editor/Cell";
import { PackageAlert } from "@/components/editor/package-alert";
import { SortableCellsProvider } from "@/components/sort/SortableCellsProvider";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { maybeAddMarimoImport } from "@/core/cells/add-missing-import";
import { MarkdownLanguageAdapter } from "@/core/codemirror/language/languages/markdown";
import { SQLLanguageAdapter } from "@/core/codemirror/language/languages/sql/sql";
import { aiEnabledAtom } from "@/core/config/config";
import { isConnectedAtom } from "@/core/network/connection";
import { useBoolean } from "@/hooks/useBoolean";
import { cn } from "@/utils/cn";
import { Functions } from "@/utils/functions";
import type { CellColumnId } from "@/utils/id-tree";
import { invariant } from "@/utils/invariant";
import {
  columnIdsAtom,
  SETUP_CELL_ID,
  useCellActions,
  useCellIds,
  useScrollKey,
} from "../../../core/cells/cells";
import { formatAll } from "../../../core/codemirror/format";
import type { AppConfig, UserConfig } from "../../../core/config/config-schema";
import type { AppMode } from "../../../core/mode";
import { useHotkey } from "../../../hooks/useHotkey";
import { type Theme, useTheme } from "../../../theme/useTheme";
import { AddCellWithAI } from "../ai/add-cell-with-ai";
import { ConnectingAlert } from "../alerts/connecting-alert";
import { FloatingOutline } from "../chrome/panels/outline/floating-outline";
import { useChromeActions } from "../chrome/state";
import { Column } from "../columns/cell-column";
import { NotebookBanner } from "../notebook-banner";
import { StdinBlockingAlert } from "../stdin-blocking-alert";
import { useFocusFirstEditor } from "./vertical-layout/useFocusFirstEditor";
import { VerticalLayoutWrapper } from "./vertical-layout/vertical-layout-wrapper";

interface CellArrayProps {
  mode: AppMode;
  userConfig: UserConfig;
  appConfig: AppConfig;
}

export const CellArray: React.FC<CellArrayProps> = (props) => {
  const columnIds = useAtomValue(columnIdsAtom);

  // Setup context for sorting
  return (
    <SortableCellsProvider multiColumn={props.appConfig.width === "columns"}>
      <SortableContext
        id="column-container"
        items={columnIds}
        strategy={horizontalListSortingStrategy}
      >
        <CellArrayInternal {...props} />
      </SortableContext>
    </SortableCellsProvider>
  );
};

const CellArrayInternal: React.FC<CellArrayProps> = ({
  mode,
  userConfig,
  appConfig,
}) => {
  const actions = useCellActions();
  const { theme } = useTheme();
  const { toggleSidebarPanel } = useChromeActions();

  // Side-effects
  useFocusFirstEditor();

  // HOTKEYS
  useHotkey("global.focusTop", actions.focusTopCell);
  useHotkey("global.focusBottom", actions.focusBottomCell);
  useHotkey("global.toggleSidebar", toggleSidebarPanel);
  useHotkey("global.foldCode", actions.foldAll);
  useHotkey("global.unfoldCode", actions.unfoldAll);
  useHotkey("global.formatAll", () => {
    formatAll();
  });
  // Catch all to avoid native OS behavior
  // Otherwise a user might try to hide a cell and accidentally hide the OS window
  useHotkey("cell.hideCode", Functions.NOOP);
  useHotkey("cell.format", Functions.NOOP);

  const cellIds = useCellIds();
  const scrollKey = useScrollKey();
  const columnIds = cellIds.getColumnIds();

  // Scroll to a cell targeted by a previous action
  const scrollToTarget = actions.scrollToTarget;
  useEffect(() => {
    if (scrollKey !== null) {
      scrollToTarget();
    }
  }, [cellIds, scrollKey, scrollToTarget]);

  return (
    <VerticalLayoutWrapper
      // 'pb' allows the user to put the cell in the middle of the screen
      className="pb-[40vh]"
      invisible={false}
      appConfig={appConfig}
      innerClassName="pr-4" // For the floating actions
    >
      <PackageAlert />
      <StartupLogsAlert />
      <StdinBlockingAlert />
      <ConnectingAlert />
      <NotebookBanner width={appConfig.width} />
      <div
        className={cn(
          appConfig.width === "columns" &&
            "grid grid-flow-col auto-cols-min gap-6",
        )}
      >
        {columnIds.map((columnId, index) => (
          <CellColumn
            key={columnId}
            columnId={columnId}
            index={index}
            columnsLength={columnIds.length}
            appConfig={appConfig}
            mode={mode}
            userConfig={userConfig}
            theme={theme}
          />
        ))}
      </div>
      <FloatingOutline />
    </VerticalLayoutWrapper>
  );
};

/**
 * A single column of cells.
 */
const CellColumn: React.FC<{
  columnId: CellColumnId;
  index: number;
  columnsLength: number;
  appConfig: AppConfig;
  mode: AppMode;
  userConfig: UserConfig;
  theme: Theme;
}> = ({
  columnId,
  index,
  columnsLength,
  appConfig,
  mode,
  userConfig,
  theme,
}) => {
  const cellIds = useCellIds();
  const column = cellIds.get(columnId);
  invariant(column, `Expected column for: ${columnId}`);

  const hasOnlyOneCell = cellIds.hasOnlyOneId();
  const hasSetupCell = cellIds.inOrderIds.includes(SETUP_CELL_ID);

  return (
    <Column
      columnId={columnId}
      index={index}
      canMoveLeft={index > 0}
      canMoveRight={index < columnsLength - 1}
      width={appConfig.width}
      canDelete={columnsLength > 1}
      footer={
        <AddCellButtons
          columnId={columnId}
          className={cn(
            appConfig.width === "columns" &&
              "opacity-0 group-hover/column:opacity-100",
          )}
        />
      }
    >
      <SortableContext
        id={`column-${index + 1}`}
        items={column.topLevelIds}
        strategy={verticalListSortingStrategy}
      >
        {/* Render the setup cell first, always */}
        {index === 0 && hasSetupCell && (
          <Cell
            key={SETUP_CELL_ID}
            cellId={SETUP_CELL_ID}
            theme={theme}
            showPlaceholder={false}
            canDelete={true}
            mode={mode}
            userConfig={userConfig}
            isCollapsed={false}
            collapseCount={0}
            canMoveX={false}
          />
        )}

        {column.topLevelIds.map((cellId) => {
          // Skip the setup cell later
          if (cellId === SETUP_CELL_ID) {
            return null;
          }

          return (
            <Cell
              key={cellId}
              cellId={cellId}
              theme={theme}
              showPlaceholder={hasOnlyOneCell}
              canDelete={!hasOnlyOneCell}
              mode={mode}
              userConfig={userConfig}
              isCollapsed={column.isCollapsed(cellId)}
              collapseCount={column.getCount(cellId)}
              canMoveX={appConfig.width === "columns"}
            />
          );
        })}
      </SortableContext>
    </Column>
  );
};

const AddCellButtons: React.FC<{
  columnId: CellColumnId;
  className?: string;
}> = ({ columnId, className }) => {
  const { createNewCell } = useCellActions();
  const [isAiButtonOpen, isAiButtonOpenActions] = useBoolean(false);
  const aiEnabled = useAtomValue(aiEnabledAtom);
  const isConnected = useAtomValue(isConnectedAtom);

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
          disabled={!isConnected}
          onClick={() =>
            createNewCell({
              cellId: { type: "__end__", columnId },
              before: false,
            })
          }
        >
          <SquareCodeIcon className="mr-2 size-4 shrink-0" />
          Python
        </Button>
        <Button
          className={buttonClass}
          variant="text"
          size="sm"
          disabled={!isConnected}
          onClick={() => {
            maybeAddMarimoImport({ autoInstantiate: true, createNewCell });

            createNewCell({
              cellId: { type: "__end__", columnId },
              before: false,
              code: new MarkdownLanguageAdapter().defaultCode,
              hideCode: true,
            });
          }}
        >
          <SquareMIcon className="mr-2 size-4 shrink-0" />
          Markdown
        </Button>
        <Button
          className={buttonClass}
          variant="text"
          size="sm"
          disabled={!isConnected}
          onClick={() => {
            maybeAddMarimoImport({ autoInstantiate: true, createNewCell });

            createNewCell({
              cellId: { type: "__end__", columnId },
              before: false,
              code: new SQLLanguageAdapter().defaultCode,
            });
          }}
        >
          <DatabaseIcon className="mr-2 size-4 shrink-0" />
          SQL
        </Button>
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
            disabled={!aiEnabled || !isConnected}
            onClick={isAiButtonOpenActions.toggle}
          >
            <SparklesIcon className="mr-2 size-4 shrink-0" />
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
            "opacity-100 w-full max-w-4xl shadow-lg shadow-(color:--blue-3)",
          className,
        )}
      >
        {renderBody()}
      </div>
    </div>
  );
};
