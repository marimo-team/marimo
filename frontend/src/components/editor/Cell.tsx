/* Copyright 2024 Marimo. All rights reserved. */
import { closeCompletion, completionStatus } from "@codemirror/autocomplete";
import type { EditorView } from "@codemirror/view";
import clsx from "clsx";
import { useAtomValue, useSetAtom } from "jotai";
import {
  HelpCircleIcon,
  MoreHorizontalIcon,
  SquareFunctionIcon,
} from "lucide-react";
import {
  type FocusEvent,
  forwardRef,
  type KeyboardEvent,
  memo,
  useCallback,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import { mergeProps } from "react-aria";
import useEvent from "react-use-event-hook";
import { StopButton } from "@/components/editor/cell/StopButton";
import { Toolbar, ToolbarItem } from "@/components/editor/cell/toolbar";
import { Tooltip, TooltipProvider } from "@/components/ui/tooltip";
import { aiCompletionCellAtom } from "@/core/ai/state";
import { outputIsLoading, outputIsStale } from "@/core/cells/cell";
import { isOutputEmpty } from "@/core/cells/outputs";
import { autocompletionKeymap } from "@/core/codemirror/cm";
import type { LanguageAdapterType } from "@/core/codemirror/language/types";
import { canCollapseOutline } from "@/core/dom/outline";
import { isErrorMime } from "@/core/mime";
import type { AppMode } from "@/core/mode";
import { connectionAtom } from "@/core/network/connection";
import { useRequestClient } from "@/core/network/requests";
import type { CellConfig, RuntimeState } from "@/core/network/types";
import { useResizeObserver } from "@/hooks/useResizeObserver";
import { cn } from "@/utils/cn";
import type { Milliseconds, Seconds } from "@/utils/time";
import {
  type CellActions,
  createUntouchedCellAtom,
  SETUP_CELL_ID,
  useCellActions,
  useCellData,
  useCellHandle,
  useCellRuntime,
} from "../../core/cells/cells";
import type { CellId } from "../../core/cells/ids";
import { isUninstantiated } from "../../core/cells/utils";
import type { UserConfig } from "../../core/config/config-schema";
import {
  isAppConnected,
  isAppInteractionDisabled,
} from "../../core/websocket/connection-utils";
import { useCellRenderCount } from "../../hooks/useCellRenderCount";
import type { Theme } from "../../theme/useTheme";
import { derefNotNull } from "../../utils/dereference";
import { Functions } from "../../utils/functions";
import { Logger } from "../../utils/Logger";
import { renderShortcut } from "../shortcuts/renderShortcut";
import { CellStatusComponent } from "./cell/CellStatus";
import { CreateCellButton } from "./cell/CreateCellButton";
import {
  CellActionsDropdown,
  type CellActionsDropdownHandle,
} from "./cell/cell-actions";
import { CellActionsContextMenu } from "./cell/cell-context-menu";
import { CellEditor } from "./cell/code/cell-editor";
import { CollapsedCellBanner, CollapseToggle } from "./cell/collapse";
import { DeleteButton } from "./cell/DeleteButton";
import { PendingDeleteConfirmation } from "./cell/PendingDeleteConfirmation";
import { RunButton } from "./cell/RunButton";
import {
  StagedAICellBackground,
  StagedAICellFooter,
} from "./cell/StagedAICell";
import { useDeleteCellCallback } from "./cell/useDeleteCell";
import { useRunCell } from "./cell/useRunCells";
import { HideCodeButton } from "./code/readonly-python-code";
import { cellDomProps } from "./common";
import { SqlValidationErrorBanner } from "./errors/sql-validation-errors";
import { useCellNavigationProps } from "./navigation/navigation";
import {
  useTemporarilyShownCode,
  useTemporarilyShownCodeActions,
} from "./navigation/state";
import { OutputArea } from "./Output";
import { ConsoleOutput } from "./output/ConsoleOutput";
import { CellDragHandle, SortableCell } from "./SortableCell";

/**
 * Hook for handling cell completion logic
 */
function useCellCompletion(
  cellRef: React.RefObject<HTMLDivElement | null>,
  editorView: React.RefObject<EditorView | null>,
) {
  // Close completion when focus leaves the cell's subtree.
  const closeCompletionHandler = useEvent((e: FocusEvent) => {
    if (
      cellRef.current !== null &&
      !cellRef.current.contains(e.relatedTarget) &&
      editorView.current !== null
    ) {
      closeCompletion(editorView.current);
    }
  });

  // Clicking on the completion info causes the editor view to lose focus,
  // because the completion is not a child of the editable editor DOM;
  // as a workaround, when a completion is active, we refocus the editor
  // on any keypress.
  //
  // See https://discuss.codemirror.net/t/adding-click-event-listener-to-autocomplete-tooltip-info-panel-is-not-working/4741
  const resumeCompletionHandler = useEvent((e: KeyboardEvent) => {
    if (
      cellRef.current !== document.activeElement ||
      editorView.current === null ||
      completionStatus(editorView.current.state) !== "active"
    ) {
      return;
    }

    for (const keymap of autocompletionKeymap) {
      if (e.key === keymap.key && keymap.run) {
        keymap.run(editorView.current);
        // preventDefault/stopPropagation: Don't process the keystrokes as
        // typing into the editor, e.g., Enter should only select the
        // completion, not also add a newline.
        e.preventDefault();
        e.stopPropagation();
        break;
      }
    }
    editorView.current.focus();
    return;
  });

  return {
    closeCompletionHandler,
    resumeCompletionHandler,
  };
}

/**
 * Hook for handling hidden cell logic.
 *
 * The code is shown if:
 * - hide_code is false
 * - the cell-editor is focused (temporarily shown)
 * - the cell is newly created (untouched)
 */
function useCellHiddenLogic({
  cellId,
  cellConfig,
  languageAdapter,
  editorView,
}: {
  cellId: CellId;
  cellConfig: CellConfig;
  languageAdapter: LanguageAdapterType | undefined;
  editorView: React.RefObject<EditorView | null>;
  editorViewParentRef: React.RefObject<HTMLDivElement | null>;
}) {
  const temporarilyVisible = useTemporarilyShownCode(cellId);
  const temporarilyShownCodeActions = useTemporarilyShownCodeActions();
  const isUntouched = useAtomValue(
    useMemo(() => createUntouchedCellAtom(cellId), [cellId]),
  );

  // The cell code is shown if the cell is not configured to be hidden or if the code is temporarily visible (i.e. when focused).
  const isCellCodeShown =
    !cellConfig.hide_code || temporarilyVisible || isUntouched;
  const isMarkdown = languageAdapter === "markdown";
  const isMarkdownCodeHidden = isMarkdown && !isCellCodeShown;

  // Callback to show the code editor temporarily
  const showHiddenCode = useEvent((opts?: { focus?: boolean }) => {
    // Already shown, do nothing
    if (isCellCodeShown) {
      return;
    }

    // Default to true
    const focus = opts?.focus ?? true;
    temporarilyShownCodeActions.add(cellId);

    if (focus) {
      editorView.current?.focus();
    }

    // Undoing happens in editor/focus/focus.ts, when the cell is blurred.
  });

  const showHiddenCodeIfMarkdown = useEvent(() => {
    if (isMarkdownCodeHidden) {
      showHiddenCode({ focus: true });
    }
  });

  return {
    isCellCodeShown,
    isMarkdown,
    isMarkdownCodeHidden,
    showHiddenCode,
    showHiddenCodeIfMarkdown,
  };
}

export type CellComponentActions = Pick<
  CellActions,
  | "updateCellCode"
  | "createNewCell"
  | "focusCell"
  | "moveCell"
  | "collapseCell"
  | "expandCell"
  | "moveToNextCell"
  | "updateCellConfig"
  | "clearSerializedEditorState"
  | "setStdinResponse"
  | "clearCellConsoleOutput"
  | "sendToBottom"
  | "sendToTop"
>;

/**
 * Imperative interface of the cell.
 */
export interface CellHandle {
  /**
   * The CodeMirror editor view.
   */
  editorView: EditorView;
  /**
   * The CodeMirror editor view, or null if it is not yet mounted.
   */
  editorViewOrNull: EditorView | null;
}

export interface CellProps {
  cellId: CellId;
  theme: Theme;
  showPlaceholder: boolean;
  mode: AppMode;
  /**
   * False only when there is only one cell in the notebook.
   */
  canDelete: boolean;
  userConfig: UserConfig;
  /**
   * If true, the cell is allowed to be moved left and right.
   */
  canMoveX: boolean;
  /**
   * If true, the cell is collapsed.
   */
  isCollapsed: boolean;
  /**
   * The number of cells in the column.
   */
  collapseCount: number;
}

const CellComponent = (props: CellProps) => {
  const { cellId, mode } = props;
  const ref = useCellHandle(cellId);

  useCellRenderCount().countRender();

  Logger.debug("Rendering Cell", cellId);

  const editorView = useRef<EditorView | null>(null);

  // An imperative interface to the code editor
  useImperativeHandle(
    ref,
    () => ({
      get editorView() {
        return derefNotNull(editorView);
      },
      get editorViewOrNull() {
        return editorView.current;
      },
    }),
    [editorView],
  );

  if (cellId === SETUP_CELL_ID) {
    return (
      <SetupCellComponent
        {...props}
        cellId={cellId}
        editorView={editorView}
        setEditorView={(ev) => {
          editorView.current = ev;
        }}
      />
    );
  }

  if (mode === "edit") {
    return (
      <EditableCellComponent
        {...props}
        cellId={cellId}
        editorView={editorView}
        setEditorView={(ev) => {
          editorView.current = ev;
        }}
      />
    );
  }

  return <ReadonlyCellComponent cellId={cellId} />;
};

const ReadonlyCellComponent = forwardRef(
  (props: { cellId: CellId }, ref: React.ForwardedRef<HTMLDivElement>) => {
    const { cellId } = props;
    const cellData = useCellData(cellId);
    const cellRuntime = useCellRuntime(cellId);

    const className = clsx("marimo-cell", "hover-actions-parent z-10", {
      published: true,
    });

    const outputIsError = isErrorMime(cellRuntime.output?.mimetype);

    // Hide the output if it's an error or stopped.
    const hidden =
      cellRuntime.errored ||
      cellRuntime.interrupted ||
      cellRuntime.stopped ||
      outputIsError;

    if (hidden) {
      return null;
    }

    return (
      <div
        tabIndex={-1}
        ref={ref}
        className={className}
        {...cellDomProps(cellId, cellData.name)}
      >
        <OutputArea
          allowExpand={false}
          forceExpand={true}
          className="output-area"
          cellId={cellId}
          output={cellRuntime.output}
          stale={outputIsStale(cellRuntime, cellData.edited)}
          loading={outputIsLoading(cellRuntime.status)}
        />
      </div>
    );
  },
);
ReadonlyCellComponent.displayName = "ReadonlyCellComponent";

const EditableCellComponent = ({
  theme,
  showPlaceholder,
  cellId,
  canDelete,
  userConfig,
  isCollapsed,
  collapseCount,
  canMoveX,
  editorView,
  setEditorView,
}: CellProps & {
  editorView: React.RefObject<EditorView | null>;
  setEditorView: (view: EditorView) => void;
}) => {
  const cellRef = useRef<HTMLDivElement>(null);
  const cellData = useCellData(cellId);
  const cellRuntime = useCellRuntime(cellId);
  const cellActionDropdownRef = useRef<CellActionsDropdownHandle>(null);
  // DOM node where the editorView will be mounted
  const editorViewParentRef = useRef<HTMLDivElement>(null);
  const cellContainerRef = useRef<HTMLDivElement>(null);

  const actions = useCellActions();
  const connection = useAtomValue(connectionAtom);
  const setAiCompletionCell = useSetAtom(aiCompletionCellAtom);
  const deleteCell = useDeleteCellCallback();
  const runCell = useRunCell(cellId);
  const { sendStdin } = useRequestClient();

  const [languageAdapter, setLanguageAdapter] = useState<LanguageAdapterType>();

  const disabledOrAncestorDisabled =
    cellData.config.disabled || cellRuntime.status === "disabled-transitively";

  const uninstantiated = isUninstantiated({
    executionTime: cellRuntime.runElapsedTimeMs ?? cellData.lastExecutionTime,
    status: cellRuntime.status,
    errored: cellRuntime.errored,
    interrupted: cellRuntime.interrupted,
    stopped: cellRuntime.stopped,
  });

  const needsRun =
    cellData.edited ||
    cellRuntime.interrupted ||
    (cellRuntime.staleInputs && !disabledOrAncestorDisabled);

  const loading = outputIsLoading(cellRuntime.status);

  // console output is cleared immediately on run, so check for queued instead
  // of loading to determine staleness
  const consoleOutputStale =
    (cellRuntime.status === "queued" ||
      cellData.edited ||
      cellRuntime.staleInputs) &&
    !cellRuntime.interrupted;

  // Callback to get the editor view.
  const getEditorView = useCallback(() => editorView.current, [editorView]);

  // Use the extracted hooks
  const { closeCompletionHandler, resumeCompletionHandler } = useCellCompletion(
    cellRef,
    editorView,
  );

  const {
    isCellCodeShown,
    isMarkdown,
    isMarkdownCodeHidden,
    showHiddenCode,
    showHiddenCodeIfMarkdown,
  } = useCellHiddenLogic({
    cellId,
    cellConfig: cellData.config,
    languageAdapter,
    editorView,
    editorViewParentRef,
  });

  // Hotkey and focus props
  const navigationProps = useCellNavigationProps(cellId, {
    canMoveX,
    editorView,
    cellActionDropdownRef,
  });
  const canCollapse = canCollapseOutline(cellRuntime.outline);
  const hasOutput = !isOutputEmpty(cellRuntime.output);
  const hasConsoleOutput = cellRuntime.consoleOutputs.length > 0;
  const cellOutput = userConfig.display.cell_output;

  const hasOutputAbove = hasOutput && cellOutput === "above";
  const hasOutputBelow = hasOutput && cellOutput === "below";

  // If the cell is too short, we need to position some icons inline to prevent overlaps.
  // This can only happen to markdown cells when the code is hidden completely
  const [isCellStatusInline, setIsCellStatusInline] = useState(false);
  const [isCellButtonsInline, setIsCellButtonsInline] = useState(false);

  useResizeObserver({
    ref: cellContainerRef,
    skip: !isMarkdown,
    onResize: (size) => {
      const cellTooShort = size.height && size.height < 68;
      const shouldBeInline =
        isMarkdownCodeHidden && (cellTooShort || cellOutput === "below");
      setIsCellStatusInline(shouldBeInline);

      if (canCollapse && shouldBeInline) {
        setIsCellButtonsInline(true);
      } else if (isCellButtonsInline) {
        setIsCellButtonsInline(false);
      }
    },
  });

  const renderHideCodeButton = (className: string) => (
    <HideCodeButton
      tooltip="Edit markdown"
      className={cn("z-20 relative", className)}
      onClick={showHiddenCode}
    />
  );

  const outputArea = hasOutput && (
    <div className="relative" onDoubleClick={showHiddenCodeIfMarkdown}>
      <div className="absolute top-5 -left-8 z-10 print:hidden">
        <CollapseToggle
          isCollapsed={isCollapsed}
          onClick={() => {
            if (isCollapsed) {
              actions.expandCell({ cellId });
            } else {
              actions.collapseCell({ cellId });
            }
          }}
          canCollapse={canCollapse}
        />
      </div>
      {isMarkdownCodeHidden && hasOutputBelow && renderHideCodeButton("top-3")}
      <OutputArea
        // Only allow expanding in edit mode
        allowExpand={true}
        // Force expand when markdown is hidden
        forceExpand={isMarkdownCodeHidden}
        className="output-area"
        cellId={cellId}
        output={cellRuntime.output}
        stale={outputIsStale(cellRuntime, cellData.edited)}
        loading={outputIsLoading(cellRuntime.status)}
      />
      {isMarkdownCodeHidden &&
        hasOutputAbove &&
        renderHideCodeButton("bottom-3")}
    </div>
  );

  const className = clsx("marimo-cell", "hover-actions-parent z-10", {
    interactive: true,
    "needs-run": needsRun,
    "has-error": cellRuntime.errored,
    stopped: cellRuntime.stopped,
    disabled: cellData.config.disabled,
    stale: cellRuntime.status === "disabled-transitively",
    borderless:
      isMarkdownCodeHidden && hasOutput && !navigationProps["data-selected"],
  });

  const handleRefactorWithAI = useEvent((opts: { prompt: string }) => {
    setAiCompletionCell({ cellId, initialPrompt: opts.prompt });
  });

  // TODO(akshayka): Move to our own Tooltip component once it's easier
  // to get the tooltip to show next to the cursor ...
  // https://github.com/radix-ui/primitives/discussions/1090
  const renderCellTitle = () => {
    if (cellData.config.disabled) {
      return "This cell is disabled";
    }
    if (cellRuntime.status === "disabled-transitively") {
      return "This cell has a disabled ancestor";
    }
    return undefined;
  };

  const isToplevel = cellRuntime.serialization?.toLowerCase() === "valid";

  return (
    <TooltipProvider>
      <CellActionsContextMenu cellId={cellId} getEditorView={getEditorView}>
        <SortableCell
          tabIndex={-1}
          ref={cellRef}
          data-status={cellRuntime.status}
          onBlur={closeCompletionHandler}
          onKeyDown={resumeCompletionHandler}
          cellId={cellId}
          canMoveX={canMoveX}
          title={renderCellTitle()}
        >
          <div
            tabIndex={-1}
            {...navigationProps}
            className={cn(
              className,
              navigationProps.className,
              "focus:ring-1 focus:ring-(--blue-7) focus:ring-offset-0",
            )}
            ref={cellContainerRef}
            {...cellDomProps(cellId, cellData.name)}
          >
            {cellOutput === "above" && outputArea}
            <div className={cn("tray")} data-hidden={isMarkdownCodeHidden}>
              <StagedAICellBackground cellId={cellId} />
              <div className="absolute right-2 -top-4 z-10">
                <CellToolbar
                  edited={cellData.edited}
                  status={cellRuntime.status}
                  cellConfig={cellData.config}
                  needsRun={needsRun}
                  hasOutput={hasOutput}
                  hasConsoleOutput={hasConsoleOutput}
                  cellActionDropdownRef={cellActionDropdownRef}
                  cellId={cellId}
                  name={cellData.name}
                  getEditorView={getEditorView}
                  onRun={runCell}
                />
              </div>
              <CellLeftSideActions
                cellId={cellId}
                className={cn(
                  isMarkdownCodeHidden && hasOutputAbove && "-top-7",
                  isMarkdownCodeHidden && hasOutputBelow && "-bottom-8",
                  isMarkdownCodeHidden &&
                    isCellButtonsInline &&
                    "-left-[3.8rem]",
                )}
                actions={actions}
              />
              <CellEditor
                theme={theme}
                showPlaceholder={showPlaceholder}
                id={cellId}
                code={cellData.code}
                config={cellData.config}
                status={cellRuntime.status}
                serializedEditorState={cellData.serializedEditorState}
                runCell={runCell}
                setEditorView={setEditorView}
                userConfig={userConfig}
                editorViewRef={editorView}
                editorViewParentRef={editorViewParentRef}
                hidden={!isCellCodeShown}
                hasOutput={hasOutput}
                showHiddenCode={showHiddenCode}
                languageAdapter={languageAdapter}
                setLanguageAdapter={setLanguageAdapter}
              />
              <CellRightSideActions
                className={cn(
                  isMarkdownCodeHidden && cellOutput === "below" && "top-14",
                )}
                edited={cellData.edited}
                status={cellRuntime.status}
                isCellStatusInline={isCellStatusInline}
                uninstantiated={uninstantiated}
                disabled={cellData.config.disabled}
                runElapsedTimeMs={cellRuntime.runElapsedTimeMs}
                runStartTimestamp={cellRuntime.runStartTimestamp}
                lastRunStartTimestamp={cellRuntime.lastRunStartTimestamp}
                staleInputs={cellRuntime.staleInputs}
                interrupted={cellRuntime.interrupted}
              />
              <div className="shoulder-bottom hover-action">
                {canDelete && isCellCodeShown && (
                  <DeleteButton
                    status={cellRuntime.status}
                    connectionState={connection.state}
                    onClick={() => {
                      if (
                        !loading &&
                        !isAppInteractionDisabled(connection.state)
                      ) {
                        deleteCell({ cellId });
                      }
                    }}
                  />
                )}
              </div>
            </div>
            <SqlValidationErrorBanner cellId={cellId} />
            {cellOutput === "below" && outputArea}
            {cellRuntime.serialization && (
              <div className="py-1 px-2 flex items-center justify-end gap-2 last:rounded-b">
                {isToplevel && (
                  <a
                    href="https://links.marimo.app/reusable-definitions"
                    target="_blank"
                    className="hover:underline text-muted-foreground text-xs font-bold"
                    rel="noopener"
                  >
                    reusable
                  </a>
                )}
                <Tooltip
                  content={
                    <span className="max-w-16 text-xs">
                      {(isToplevel &&
                        "This function or class can be imported into other Python notebooks or modules.") || (
                        <>
                          This definition can't be reused in other Python
                          modules:
                          <br />
                          <br />
                          <pre>{cellRuntime.serialization}</pre>
                          <br />
                          Click this icon to learn more.
                        </>
                      )}
                    </span>
                  }
                >
                  {isToplevel ? (
                    <a
                      href="https://links.marimo.app/reusable-definitions"
                      target="_blank"
                      rel="noopener"
                    >
                      <SquareFunctionIcon
                        size={16}
                        strokeWidth={1.5}
                        className="rounded-lg text-muted-foreground"
                      />
                    </a>
                  ) : (
                    <a
                      href="https://links.marimo.app/reusable-definitions"
                      target="_blank"
                      rel="noopener"
                    >
                      <HelpCircleIcon
                        size={16}
                        strokeWidth={1.5}
                        className="rounded-lg text-muted-foreground"
                      />
                    </a>
                  )}
                </Tooltip>
              </div>
            )}
            <ConsoleOutput
              consoleOutputs={cellRuntime.consoleOutputs}
              stale={consoleOutputStale}
              // Empty name if serialization triggered
              cellName={cellRuntime.serialization ? "_" : cellData.name}
              onRefactorWithAI={handleRefactorWithAI}
              onClear={() => {
                actions.clearCellConsoleOutput({ cellId });
              }}
              onSubmitDebugger={(text, index) => {
                actions.setStdinResponse({
                  cellId,
                  response: text,
                  outputIndex: index,
                });
                sendStdin({ text });
              }}
              cellId={cellId}
              debuggerActive={cellRuntime.debuggerActive}
            />
            <PendingDeleteConfirmation cellId={cellId} />
          </div>
          <StagedAICellFooter cellId={cellId} />
          {isCollapsed && (
            <CollapsedCellBanner
              onClick={() => actions.expandCell({ cellId })}
              count={collapseCount}
              cellId={cellId}
            />
          )}
        </SortableCell>
      </CellActionsContextMenu>
    </TooltipProvider>
  );
};

const CellRightSideActions = memo(
  (props: {
    className?: string;
    disabled: boolean | undefined;
    edited: boolean;
    interrupted: boolean;
    isCellStatusInline: boolean;
    lastRunStartTimestamp: Seconds | null;
    runElapsedTimeMs: Milliseconds | null;
    runStartTimestamp: Seconds | null;
    staleInputs: boolean;
    status: RuntimeState;
    uninstantiated: boolean;
  }) => {
    const {
      className,
      disabled = false,
      edited,
      interrupted,
      isCellStatusInline,
      lastRunStartTimestamp,
      runElapsedTimeMs,
      runStartTimestamp,
      staleInputs,
      status,
      uninstantiated,
    } = props;

    const cellStatusComponent = (
      <CellStatusComponent
        status={status}
        staleInputs={staleInputs}
        interrupted={interrupted}
        editing={true}
        edited={edited}
        disabled={disabled}
        elapsedTime={runElapsedTimeMs}
        runStartTimestamp={runStartTimestamp}
        uninstantiated={uninstantiated}
        lastRunStartTimestamp={lastRunStartTimestamp}
      />
    );

    return (
      <div className={cn("shoulder-right z-20", className)}>
        {!isCellStatusInline && cellStatusComponent}
        <div className="flex gap-2 items-end">
          <CellDragHandle />
          {isCellStatusInline && cellStatusComponent}
        </div>
      </div>
    );
  },
);

CellRightSideActions.displayName = "CellRightSideActions";

const CellLeftSideActions = memo(
  (props: {
    className?: string;
    cellId: CellId;
    actions: CellComponentActions;
  }) => {
    const connection = useAtomValue(connectionAtom);
    const { className, actions, cellId } = props;

    const createBelow = useEvent(
      (opts: { code?: string; hideCode?: boolean } = {}) =>
        actions.createNewCell({ cellId, before: false, ...opts }),
    );
    const createAbove = useEvent(
      (opts: { code?: string; hideCode?: boolean } = {}) =>
        actions.createNewCell({ cellId, before: true, ...opts }),
    );

    const isConnected = isAppConnected(connection.state);

    return (
      <div
        className={cn(
          "absolute flex flex-col gap-[2px] justify-center h-full left-[-34px] z-20",
          className,
        )}
      >
        <CreateCellButton
          tooltipContent={renderShortcut("cell.createAbove")}
          connectionState={connection.state}
          onClick={isConnected ? createAbove : undefined}
        />
        <div className="flex-1" />
        <CreateCellButton
          tooltipContent={renderShortcut("cell.createBelow")}
          connectionState={connection.state}
          onClick={isConnected ? createBelow : undefined}
        />
      </div>
    );
  },
);

CellLeftSideActions.displayName = "CellLeftSideActions";

interface CellToolbarProps {
  edited: boolean;
  status: RuntimeState;
  cellConfig: CellConfig;
  needsRun: boolean;
  hasOutput: boolean;
  hasConsoleOutput: boolean;
  cellActionDropdownRef: React.RefObject<CellActionsDropdownHandle | null>;
  cellId: CellId;
  name: string;
  includeCellActions?: boolean;
  getEditorView: () => EditorView | null;
  onRun: () => void;
}

const CellToolbar = memo(
  ({
    edited,
    status,
    cellConfig,
    needsRun,
    hasOutput,
    hasConsoleOutput,
    onRun,
    cellActionDropdownRef,
    cellId,
    getEditorView,
    name,
    includeCellActions = true,
  }: CellToolbarProps) => {
    const connection = useAtomValue(connectionAtom);
    const isConnected = isAppConnected(connection.state);

    return (
      <Toolbar
        className={cn(
          // Show the toolbar on hover, or when the cell needs to be run
          !needsRun && "hover-action",
        )}
      >
        <RunButton
          edited={edited}
          onClick={isConnected ? onRun : Functions.NOOP}
          connectionState={connection.state}
          status={status}
          config={cellConfig}
          needsRun={needsRun}
        />
        <StopButton status={status} connectionState={connection.state} />
        {includeCellActions && (
          <CellActionsDropdown
            ref={cellActionDropdownRef}
            cellId={cellId}
            status={status}
            getEditorView={getEditorView}
            name={name}
            config={cellConfig}
            hasOutput={hasOutput}
            hasConsoleOutput={hasConsoleOutput}
          >
            <ToolbarItem
              variant={"green"}
              tooltip={null}
              data-testid="cell-actions-button"
            >
              <MoreHorizontalIcon strokeWidth={1.5} />
            </ToolbarItem>
          </CellActionsDropdown>
        )}
      </Toolbar>
    );
  },
);

CellToolbar.displayName = "CellToolbar";

/**
 * A cell that is not allowed to be deleted or moved.
 * It also has no outputs.
 */
const SetupCellComponent = ({
  theme,
  showPlaceholder,
  cellId,
  canDelete,
  userConfig,
  canMoveX,
  editorView,
  setEditorView,
}: CellProps & {
  editorView: React.RefObject<EditorView | null>;
  setEditorView: (view: EditorView) => void;
}) => {
  const cellRef = useRef<HTMLDivElement>(null);
  const cellData = useCellData(cellId);
  const cellRuntime = useCellRuntime(cellId);
  const cellActionDropdownRef = useRef<CellActionsDropdownHandle>(null);
  // DOM node where the editorView will be mounted
  const editorViewParentRef = useRef<HTMLDivElement>(null);
  const connection = useAtomValue(connectionAtom);

  const actions = useCellActions();
  const requestClient = useRequestClient();
  const deleteCell = useDeleteCellCallback();
  const setAiCompletionCell = useSetAtom(aiCompletionCellAtom);
  const runCell = useRunCell(cellId);

  const disabledOrAncestorDisabled =
    cellData.config.disabled || cellRuntime.status === "disabled-transitively";

  const uninstantiated = isUninstantiated({
    executionTime: cellRuntime.runElapsedTimeMs ?? cellData.lastExecutionTime,
    status: cellRuntime.status,
    errored: cellRuntime.errored,
    interrupted: cellRuntime.interrupted,
    stopped: cellRuntime.stopped,
  });

  const needsRun =
    cellData.edited ||
    cellRuntime.interrupted ||
    (cellRuntime.staleInputs && !disabledOrAncestorDisabled);
  const loading =
    cellRuntime.status === "running" || cellRuntime.status === "queued";

  // console output is cleared immediately on run, so check for queued instead
  // of loading to determine staleness
  const consoleOutputStale =
    (cellRuntime.status === "queued" ||
      cellData.edited ||
      cellRuntime.staleInputs) &&
    !cellRuntime.interrupted;

  // Callback to get the editor view.
  const getEditorView = useCallback(() => editorView.current, [editorView]);

  const { isCellCodeShown, showHiddenCode } = useCellHiddenLogic({
    cellId,
    cellConfig: cellData.config,
    languageAdapter: "python",
    editorView,
    editorViewParentRef,
  });

  // Use the extracted hooks
  const { closeCompletionHandler, resumeCompletionHandler } = useCellCompletion(
    cellRef,
    editorView,
  );

  // Hotkeys and focus props
  const navigationProps = useCellNavigationProps(cellId, {
    canMoveX,
    editorView,
    cellActionDropdownRef,
  });
  const hasOutput = !isOutputEmpty(cellRuntime.output);
  const hasConsoleOutput = cellRuntime.consoleOutputs.length > 0;
  const isErrorOutput = isErrorMime(cellRuntime.output?.mimetype);

  const className = clsx(
    "marimo-cell",
    "hover-actions-parent z-10 border shadow-sm",
    "border-(--blue-5)! rounded-sm!",
    {
      "needs-run": needsRun,
      "has-error": cellRuntime.errored,
      stopped: cellRuntime.stopped,
    },
  );

  const handleRefactorWithAI = useEvent((opts: { prompt: string }) => {
    setAiCompletionCell({ cellId, initialPrompt: opts.prompt });
  });

  // TODO(akshayka): Move to our own Tooltip component once it's easier
  // to get the tooltip to show next to the cursor ...
  // https://github.com/radix-ui/primitives/discussions/1090
  const renderCellTitle = () => {
    if (cellData.config.disabled) {
      return "This cell is disabled";
    }
    if (cellRuntime.status === "disabled-transitively") {
      return "This cell has a disabled ancestor";
    }
    return undefined;
  };

  return (
    <TooltipProvider>
      <CellActionsContextMenu cellId={cellId} getEditorView={getEditorView}>
        <div
          data-status={cellRuntime.status}
          ref={cellRef}
          {...mergeProps(navigationProps, {
            className,
            onBlur: closeCompletionHandler,
            onKeyDown: resumeCompletionHandler,
          })}
          {...cellDomProps(cellId, cellData.name)}
          title={renderCellTitle()}
          data-setup-cell={true}
        >
          <div className={cn("tray")} data-hidden={!isCellCodeShown}>
            <div className="absolute right-2 -top-4 z-10">
              <CellToolbar
                edited={cellData.edited}
                status={cellRuntime.status}
                cellConfig={cellData.config}
                needsRun={needsRun}
                hasOutput={hasOutput}
                hasConsoleOutput={hasConsoleOutput}
                cellActionDropdownRef={cellActionDropdownRef}
                cellId={cellId}
                name={cellData.name}
                getEditorView={getEditorView}
                onRun={runCell}
                includeCellActions={true}
              />
            </div>
            <CellEditor
              theme={theme}
              showPlaceholder={showPlaceholder}
              id={cellId}
              code={cellData.code}
              config={cellData.config}
              status={cellRuntime.status}
              serializedEditorState={cellData.serializedEditorState}
              runCell={runCell}
              setEditorView={setEditorView}
              userConfig={userConfig}
              editorViewRef={editorView}
              editorViewParentRef={editorViewParentRef}
              hidden={!isCellCodeShown}
              hasOutput={hasOutput}
              showHiddenCode={showHiddenCode}
              languageAdapter={"python"}
              setLanguageAdapter={Functions.NOOP}
              showLanguageToggles={false}
            />
            <CellRightSideActions
              edited={cellData.edited}
              status={cellRuntime.status}
              isCellStatusInline={false}
              uninstantiated={uninstantiated}
              disabled={cellData.config.disabled}
              runElapsedTimeMs={cellRuntime.runElapsedTimeMs}
              runStartTimestamp={cellRuntime.runStartTimestamp}
              lastRunStartTimestamp={cellRuntime.lastRunStartTimestamp}
              staleInputs={cellRuntime.staleInputs}
              interrupted={cellRuntime.interrupted}
            />
            <div className="shoulder-bottom hover-action">
              {canDelete && (
                <DeleteButton
                  connectionState={connection.state}
                  status={cellRuntime.status}
                  onClick={() => {
                    if (
                      !loading &&
                      !isAppInteractionDisabled(connection.state)
                    ) {
                      deleteCell({ cellId });
                    }
                  }}
                />
              )}
            </div>
          </div>
          <div className="py-1 px-2 flex justify-end gap-2 last:rounded-b">
            <span className="text-muted-foreground text-xs font-bold">
              setup cell
            </span>
            <Tooltip
              content={
                <span className="max-w-16">
                  This <b>setup cell</b> is guaranteed to run before all other
                  cells. Include <br />
                  initialization or imports and constants required by top-level
                  functions.
                </span>
              }
            >
              <HelpCircleIcon
                size={16}
                strokeWidth={1.5}
                className="rounded-lg text-muted-foreground"
              />
            </Tooltip>
          </div>
          {isErrorOutput && (
            <OutputArea
              allowExpand={true}
              forceExpand={true}
              className="output-area"
              cellId={cellId}
              output={cellRuntime.output}
              stale={false}
              loading={loading}
            />
          )}
          <ConsoleOutput
            consoleOutputs={cellRuntime.consoleOutputs}
            stale={consoleOutputStale}
            // Don't show name
            cellName={"_"}
            onRefactorWithAI={handleRefactorWithAI}
            onClear={() => {
              actions.clearCellConsoleOutput({ cellId });
            }}
            onSubmitDebugger={(text, index) => {
              actions.setStdinResponse({
                cellId,
                response: text,
                outputIndex: index,
              });
              requestClient.sendStdin({ text });
            }}
            cellId={cellId}
            debuggerActive={cellRuntime.debuggerActive}
          />
        </div>
      </CellActionsContextMenu>
    </TooltipProvider>
  );
};

export const Cell = memo(CellComponent);
