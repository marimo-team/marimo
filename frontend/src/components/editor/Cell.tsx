/* Copyright 2024 Marimo. All rights reserved. */
import { closeCompletion, completionStatus } from "@codemirror/autocomplete";
import type { EditorView } from "@codemirror/view";
import clsx from "clsx";
import { useAtom, useAtomValue, useSetAtom } from "jotai";
import { ScopeProvider } from "jotai-scope";
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
import { sendStdin } from "@/core/network/requests";
import type { CellConfig, RuntimeState } from "@/core/network/types";
import { useResizeObserver } from "@/hooks/useResizeObserver";
import { cn } from "@/utils/cn";
import type { Milliseconds, Seconds } from "@/utils/time";
import {
  type CellActions,
  createUntouchedCellAtom,
  SETUP_CELL_ID,
} from "../../core/cells/cells";
import type { CellId } from "../../core/cells/ids";
import type { CellData, CellRuntimeState } from "../../core/cells/types";
import { isUninstantiated } from "../../core/cells/utils";
import type { UserConfig } from "../../core/config/config-schema";
import {
  isAppConnected,
  isAppInteractionDisabled,
} from "../../core/websocket/connection-utils";
import type { WebSocketState } from "../../core/websocket/types";
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
import { useRunCell } from "./cell/useRunCells";
import { HideCodeButton } from "./code/readonly-python-code";
import { cellDomProps } from "./common";
import { useCellNavigationProps } from "./navigation/navigation";
import { temporarilyShownCodeAtom } from "./navigation/state";
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
  const [temporarilyVisible, setTemporarilyVisible] = useAtom(
    temporarilyShownCodeAtom,
  );
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
    setTemporarilyVisible(true);

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

export interface CellProps
  extends Pick<
      CellRuntimeState,
      | "consoleOutputs"
      | "status"
      | "outline"
      | "output"
      | "errored"
      | "interrupted"
      | "stopped"
      | "staleInputs"
      | "runStartTimestamp"
      | "lastRunStartTimestamp"
      | "serialization"
      | "runElapsedTimeMs"
      | "debuggerActive"
    >,
    Pick<
      CellData,
      "id" | "code" | "edited" | "config" | "name" | "serializedEditorState"
    > {
  actions: CellComponentActions;
  deleteCell: CellActions["deleteCell"];
  theme: Theme;
  showPlaceholder: boolean;
  mode: AppMode;
  connectionState: WebSocketState;
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

const CellComponent = (
  props: CellProps,
  ref: React.ForwardedRef<CellHandle>,
) => {
  const {
    status,
    output,
    runStartTimestamp,
    interrupted,
    staleInputs,
    edited,
    id,
    mode,
  } = props;

  useCellRenderCount().countRender();

  Logger.debug("Rendering Cell", id);
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

  const outputStale = outputIsStale(
    { status, output, runStartTimestamp, interrupted, staleInputs },
    edited,
  );

  const loading = outputIsLoading(status);

  if (id === SETUP_CELL_ID) {
    return (
      <SetupCellComponent
        {...props}
        editorView={editorView}
        setEditorView={(ev) => {
          editorView.current = ev;
        }}
        outputStale={outputStale}
      />
    );
  }

  if (mode === "edit") {
    return (
      <ScopeProvider atoms={[temporarilyShownCodeAtom]}>
        <EditableCellComponent
          {...props}
          editorView={editorView}
          setEditorView={(ev) => {
            editorView.current = ev;
          }}
          outputStale={outputStale}
        />
      </ScopeProvider>
    );
  }

  return (
    <ReadonlyCellComponent
      {...props}
      outputStale={outputStale}
      outputLoading={loading}
    />
  );
};

const ReadonlyCellComponent = forwardRef(
  (
    props: Pick<
      CellProps,
      "id" | "output" | "interrupted" | "errored" | "stopped" | "name"
    > & {
      outputStale: boolean;
      outputLoading: boolean;
    },
    ref: React.ForwardedRef<HTMLDivElement>,
  ) => {
    const {
      id: cellId,
      output,
      interrupted,
      errored,
      stopped,
      name,
      outputStale,
      outputLoading,
    } = props;

    const className = clsx("marimo-cell", "hover-actions-parent z-10", {
      published: true,
    });

    const outputIsError = isErrorMime(output?.mimetype);

    // Hide the output if it's an error or stopped.
    const hidden = errored || interrupted || stopped || outputIsError;
    if (hidden) {
      return null;
    }

    return (
      <div
        tabIndex={-1}
        ref={ref}
        className={className}
        {...cellDomProps(cellId, name)}
      >
        <OutputArea
          allowExpand={false}
          forceExpand={true}
          output={output}
          className="output-area"
          cellId={cellId}
          stale={outputStale}
          loading={outputLoading}
        />
      </div>
    );
  },
);
ReadonlyCellComponent.displayName = "ReadonlyCellComponent";

const EditableCellComponent = ({
  theme,
  showPlaceholder,
  id: cellId,
  code,
  output,
  consoleOutputs,
  status,
  runStartTimestamp,
  lastRunStartTimestamp,
  runElapsedTimeMs,
  edited,
  interrupted,
  errored,
  stopped,
  staleInputs,
  serializedEditorState,
  serialization,
  debuggerActive,
  connectionState,
  canDelete,
  actions,
  deleteCell,
  userConfig,
  outline,
  isCollapsed,
  collapseCount,
  config: cellConfig,
  canMoveX,
  name,
  editorView,
  setEditorView,
  outputStale,
}: CellProps & {
  editorView: React.RefObject<EditorView | null>;
  setEditorView: (view: EditorView) => void;
  outputStale: boolean;
}) => {
  const cellRef = useRef<HTMLDivElement>(null);
  const cellActionDropdownRef = useRef<CellActionsDropdownHandle>(null);
  // DOM node where the editorView will be mounted
  const editorViewParentRef = useRef<HTMLDivElement>(null);
  const cellContainerRef = useRef<HTMLDivElement>(null);

  const setAiCompletionCell = useSetAtom(aiCompletionCellAtom);
  const runCell = useRunCell(cellId);

  const [languageAdapter, setLanguageAdapter] = useState<LanguageAdapterType>();

  const disabledOrAncestorDisabled =
    cellConfig.disabled || status === "disabled-transitively";

  const uninstantiated = isUninstantiated({
    executionTime: runElapsedTimeMs,
    status,
    errored,
    interrupted,
    stopped,
  });

  const needsRun =
    edited || interrupted || (staleInputs && !disabledOrAncestorDisabled);
  const loading = outputIsLoading(status);

  // console output is cleared immediately on run, so check for queued instead
  // of loading to determine staleness
  const consoleOutputStale =
    (status === "queued" || edited || staleInputs) && !interrupted;

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
    cellConfig,
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
  const canCollapse = canCollapseOutline(outline);
  const hasOutput = !isOutputEmpty(output);
  const hasConsoleOutput = consoleOutputs.length > 0;
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
        output={output}
        className="output-area"
        cellId={cellId}
        stale={outputStale}
        loading={loading}
      />
      {isMarkdownCodeHidden &&
        hasOutputAbove &&
        renderHideCodeButton("bottom-3")}
    </div>
  );

  const className = clsx("marimo-cell", "hover-actions-parent z-10", {
    interactive: true,
    "needs-run": needsRun,
    "has-error": errored,
    stopped: stopped,
    disabled: cellConfig.disabled,
    stale: status === "disabled-transitively",
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
    if (cellConfig.disabled) {
      return "This cell is disabled";
    }
    if (status === "disabled-transitively") {
      return "This cell has a disabled ancestor";
    }
    return undefined;
  };

  const isToplevel = !!(
    serialization && serialization.toLowerCase() === "valid"
  );

  return (
    <TooltipProvider>
      <CellActionsContextMenu
        cellId={cellId}
        config={cellConfig}
        status={status}
        getEditorView={getEditorView}
        hasOutput={hasOutput}
        hasConsoleOutput={hasConsoleOutput}
        name={name}
      >
        <SortableCell
          tabIndex={-1}
          ref={cellRef}
          data-status={status}
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
              "focus:ring-1 focus:ring-[var(--blue-7)] focus:ring-offset-0",
            )}
            ref={cellContainerRef}
            {...cellDomProps(cellId, name)}
          >
            {cellOutput === "above" && outputArea}
            <div className={cn("tray")} data-hidden={isMarkdownCodeHidden}>
              <div className="absolute right-2 -top-4 z-10">
                <CellToolbar
                  edited={edited}
                  connectionState={connectionState}
                  status={status}
                  cellConfig={cellConfig}
                  needsRun={needsRun}
                  hasOutput={hasOutput}
                  hasConsoleOutput={hasConsoleOutput}
                  cellActionDropdownRef={cellActionDropdownRef}
                  cellId={cellId}
                  name={name}
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
                connectionState={connectionState}
                actions={actions}
              />
              <CellEditor
                theme={theme}
                showPlaceholder={showPlaceholder}
                id={cellId}
                code={code}
                config={cellConfig}
                status={status}
                serializedEditorState={serializedEditorState}
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
                edited={edited}
                status={status}
                isCellStatusInline={isCellStatusInline}
                uninstantiated={uninstantiated}
                disabled={cellConfig.disabled}
                runElapsedTimeMs={runElapsedTimeMs}
                runStartTimestamp={runStartTimestamp}
                lastRunStartTimestamp={lastRunStartTimestamp}
                staleInputs={staleInputs}
                interrupted={interrupted}
              />
              <div className="shoulder-bottom hover-action">
                {canDelete && isCellCodeShown && (
                  <DeleteButton
                    connectionState={connectionState}
                    status={status}
                    onClick={() => {
                      if (
                        !loading &&
                        !isAppInteractionDisabled(connectionState)
                      ) {
                        deleteCell({ cellId });
                      }
                    }}
                  />
                )}
              </div>
            </div>
            {cellOutput === "below" && outputArea}
            {serialization && (
              <a
                href="https://links.marimo.app/reusable-definitions"
                target="_blank"
                className="hover:underline py-1 px-2 flex items-center justify-end gap-2 last:rounded-b"
                rel="noopener"
              >
                {isToplevel && (
                  <span className="text-muted-foreground text-xs font-bold">
                    reusable
                  </span>
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
                          <pre>{serialization}</pre>
                          <br />
                          Click this icon to learn more.
                        </>
                      )}
                    </span>
                  }
                >
                  {(isToplevel && (
                    <SquareFunctionIcon
                      size={16}
                      strokeWidth={1.5}
                      className="rounded-lg text-muted-foreground"
                    />
                  )) || (
                    <HelpCircleIcon
                      size={16}
                      strokeWidth={1.5}
                      className="rounded-lg text-muted-foreground"
                    />
                  )}
                </Tooltip>
              </a>
            )}
            <ConsoleOutput
              consoleOutputs={consoleOutputs}
              stale={consoleOutputStale}
              // Empty name if serialization triggered
              cellName={serialization ? "_" : name}
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
              debuggerActive={debuggerActive}
            />
            <PendingDeleteConfirmation cellId={cellId} />
          </div>
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

const CellRightSideActions = (props: {
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
};

const CellLeftSideActions = (props: {
  className?: string;
  cellId: CellId;
  connectionState: WebSocketState;
  actions: CellComponentActions;
}) => {
  const { className, connectionState, actions, cellId } = props;

  const createBelow = useEvent(
    (opts: { code?: string; hideCode?: boolean } = {}) =>
      actions.createNewCell({ cellId, before: false, ...opts }),
  );
  const createAbove = useEvent(
    (opts: { code?: string; hideCode?: boolean } = {}) =>
      actions.createNewCell({ cellId, before: true, ...opts }),
  );

  const isConnected = isAppConnected(connectionState);

  return (
    <div
      className={cn(
        "absolute flex flex-col gap-[2px] justify-center h-full left-[-34px] z-20",
        className,
      )}
    >
      <CreateCellButton
        tooltipContent={renderShortcut("cell.createAbove")}
        connectionState={connectionState}
        onClick={isConnected ? createAbove : undefined}
      />
      <div className="flex-1" />
      <CreateCellButton
        tooltipContent={renderShortcut("cell.createBelow")}
        connectionState={connectionState}
        onClick={isConnected ? createBelow : undefined}
      />
    </div>
  );
};

interface CellToolbarProps {
  edited: boolean;
  connectionState: WebSocketState;
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

const CellToolbar = ({
  edited,
  connectionState,
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
  const isConnected = isAppConnected(connectionState);

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
        connectionState={connectionState}
        status={status}
        config={cellConfig}
        needsRun={needsRun}
      />
      <StopButton status={status} connectionState={connectionState} />
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
};

/**
 * A cell that is not allowed to be deleted or moved.
 * It also has no outputs.
 */
const SetupCellComponent = ({
  theme,
  showPlaceholder,
  id: cellId,
  code,
  output,
  consoleOutputs,
  status,
  runStartTimestamp,
  lastRunStartTimestamp,
  runElapsedTimeMs,
  edited,
  interrupted,
  errored,
  stopped,
  staleInputs,
  serializedEditorState,
  debuggerActive,
  connectionState,
  canDelete,
  actions,
  deleteCell,
  userConfig,
  config: cellConfig,
  canMoveX,
  name,
  editorView,
  setEditorView,
}: CellProps & {
  editorView: React.RefObject<EditorView | null>;
  setEditorView: (view: EditorView) => void;
  outputStale: boolean;
}) => {
  const cellRef = useRef<HTMLDivElement>(null);
  const cellActionDropdownRef = useRef<CellActionsDropdownHandle>(null);
  // DOM node where the editorView will be mounted
  const editorViewParentRef = useRef<HTMLDivElement>(null);

  const setAiCompletionCell = useSetAtom(aiCompletionCellAtom);
  const runCell = useRunCell(cellId);

  const disabledOrAncestorDisabled =
    cellConfig.disabled || status === "disabled-transitively";

  const uninstantiated = isUninstantiated({
    executionTime: runElapsedTimeMs,
    status,
    errored,
    interrupted,
    stopped,
  });

  const needsRun =
    edited || interrupted || (staleInputs && !disabledOrAncestorDisabled);
  const loading = status === "running" || status === "queued";

  // console output is cleared immediately on run, so check for queued instead
  // of loading to determine staleness
  const consoleOutputStale =
    (status === "queued" || edited || staleInputs) && !interrupted;

  // Callback to get the editor view.
  const getEditorView = useCallback(() => editorView.current, [editorView]);

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
  const hasOutput = !isOutputEmpty(output);
  const hasConsoleOutput = consoleOutputs.length > 0;
  const isErrorOutput = isErrorMime(output?.mimetype);

  const className = clsx(
    "marimo-cell",
    "hover-actions-parent z-10 border shadow-sm",
    "!border-[var(--blue-5)] !rounded-sm",
    {
      "needs-run": needsRun,
      "has-error": errored,
      stopped: stopped,
    },
  );

  const handleRefactorWithAI = useEvent((opts: { prompt: string }) => {
    setAiCompletionCell({ cellId, initialPrompt: opts.prompt });
  });

  // TODO(akshayka): Move to our own Tooltip component once it's easier
  // to get the tooltip to show next to the cursor ...
  // https://github.com/radix-ui/primitives/discussions/1090
  const renderCellTitle = () => {
    if (cellConfig.disabled) {
      return "This cell is disabled";
    }
    if (status === "disabled-transitively") {
      return "This cell has a disabled ancestor";
    }
    return undefined;
  };

  return (
    <TooltipProvider>
      <CellActionsContextMenu
        cellId={cellId}
        config={cellConfig}
        status={status}
        getEditorView={getEditorView}
        hasOutput={hasOutput}
        hasConsoleOutput={hasConsoleOutput}
        name={name}
      >
        <div
          data-status={status}
          ref={cellRef}
          {...mergeProps(navigationProps, {
            className,
            onBlur: closeCompletionHandler,
            onKeyDown: resumeCompletionHandler,
          })}
          {...cellDomProps(cellId, name)}
          title={renderCellTitle()}
          data-setup-cell={true}
        >
          <div className={cn("tray")} data-hidden={false}>
            <div className="absolute right-2 -top-4 z-10">
              <CellToolbar
                edited={edited}
                connectionState={connectionState}
                status={status}
                cellConfig={cellConfig}
                needsRun={needsRun}
                hasOutput={hasOutput}
                hasConsoleOutput={hasConsoleOutput}
                cellActionDropdownRef={cellActionDropdownRef}
                cellId={cellId}
                name={name}
                getEditorView={getEditorView}
                onRun={runCell}
                includeCellActions={false}
              />
            </div>
            <CellEditor
              theme={theme}
              showPlaceholder={showPlaceholder}
              id={cellId}
              code={code}
              config={cellConfig}
              status={status}
              serializedEditorState={serializedEditorState}
              runCell={runCell}
              setEditorView={setEditorView}
              userConfig={userConfig}
              editorViewRef={editorView}
              editorViewParentRef={editorViewParentRef}
              hidden={false}
              hasOutput={hasOutput}
              showHiddenCode={Functions.NOOP}
              languageAdapter={"python"}
              setLanguageAdapter={Functions.NOOP}
              showLanguageToggles={false}
            />
            <CellRightSideActions
              edited={edited}
              status={status}
              isCellStatusInline={false}
              uninstantiated={uninstantiated}
              disabled={cellConfig.disabled}
              runElapsedTimeMs={runElapsedTimeMs}
              runStartTimestamp={runStartTimestamp}
              lastRunStartTimestamp={lastRunStartTimestamp}
              staleInputs={staleInputs}
              interrupted={interrupted}
            />
            <div className="shoulder-bottom hover-action">
              {canDelete && (
                <DeleteButton
                  connectionState={connectionState}
                  status={status}
                  onClick={() => {
                    if (
                      !loading &&
                      !isAppInteractionDisabled(connectionState)
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
              output={output}
              className="output-area"
              cellId={cellId}
              stale={false}
              loading={loading}
            />
          )}
          <ConsoleOutput
            consoleOutputs={consoleOutputs}
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
              sendStdin({ text });
            }}
            cellId={cellId}
            debuggerActive={debuggerActive}
          />
        </div>
      </CellActionsContextMenu>
    </TooltipProvider>
  );
};

export const Cell = memo(forwardRef<CellHandle, CellProps>(CellComponent));
