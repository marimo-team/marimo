/* Copyright 2024 Marimo. All rights reserved. */
import { closeCompletion, completionStatus } from "@codemirror/autocomplete";
import type { EditorView } from "@codemirror/view";
import {
  memo,
  type FocusEvent,
  type KeyboardEvent,
  forwardRef,
  useCallback,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import { saveCellConfig, sendStdin } from "@/core/network/requests";
import { autocompletionKeymap } from "@/core/codemirror/cm";
import type { UserConfig } from "../../core/config/config-schema";
import type { CellData, CellRuntimeState } from "../../core/cells/types";
import type { CellActions } from "../../core/cells/cells";
import { isUninstantiated } from "../../core/cells/utils";
import { derefNotNull } from "../../utils/dereference";
import { OutputArea } from "./Output";
import { ConsoleOutput } from "./output/ConsoleOutput";
import { CreateCellButton } from "./cell/CreateCellButton";
import { RunButton } from "./cell/RunButton";
import { DeleteButton } from "./cell/DeleteButton";
import { CellStatusComponent } from "./cell/CellStatus";
import clsx from "clsx";
import { renderShortcut } from "../shortcuts/renderShortcut";
import { useCellRenderCount } from "../../hooks/useCellRenderCount";
import { Functions } from "../../utils/functions";
import { Logger } from "../../utils/Logger";
import { CellDragHandle, SortableCell } from "./SortableCell";
import { type CellId, HTMLCellId } from "../../core/cells/ids";
import type { Theme } from "../../theme/useTheme";
import {
  CellActionsDropdown,
  type CellActionsDropdownHandle,
} from "./cell/cell-actions";
import { CellActionsContextMenu } from "./cell/cell-context-menu";
import type { AppMode } from "@/core/mode";
import useEvent from "react-use-event-hook";
import { CellEditor } from "./cell/code/cell-editor";
import { outputIsStale } from "@/core/cells/cell";
import { isOutputEmpty } from "@/core/cells/outputs";
import { useHotkeysOnElement, useKeydownOnElement } from "@/hooks/useHotkey";
import { useSetAtom } from "jotai";
import { aiCompletionCellAtom } from "@/core/ai/state";
import { CollapsedCellBanner, CollapseToggle } from "./cell/collapse";
import { canCollapseOutline } from "@/core/dom/outline";
import { StopButton } from "@/components/editor/cell/StopButton";
import type { CellConfig, RuntimeState } from "@/core/network/types";
import { MoreHorizontalIcon } from "lucide-react";
import { Toolbar, ToolbarItem } from "@/components/editor/cell/toolbar";
import { cn } from "@/utils/cn";
import { isErrorMime } from "@/core/mime";
import { HideCodeButton } from "./code/readonly-python-code";
import { useResizeObserver } from "@/hooks/useResizeObserver";
import type { LanguageAdapterType } from "@/core/codemirror/language/types";
import { Events } from "@/utils/events";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useRunCell } from "./cell/useRunCells";

/**
 * Hook for handling cell completion logic
 */
function useCellCompletion(
  cellRef: React.RefObject<HTMLDivElement>,
  editorView: React.RefObject<EditorView>,
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
 * Hook for handling cell hotkeys
 */
function useCellHotkeys(
  cellRef: React.RefObject<HTMLDivElement> | null,
  cellId: CellId,
  runCell: () => void,
  actions: CellComponentActions,
  canMoveX: boolean,
  cellConfig: CellConfig,
  editorView: React.RefObject<EditorView | null>,
  setAiCompletionCell: ReturnType<
    typeof useSetAtom<typeof aiCompletionCellAtom>
  >,
  cellActionDropdownRef: React.RefObject<CellActionsDropdownHandle>,
) {
  useHotkeysOnElement(cellRef, {
    "cell.run": runCell,
    "cell.runAndNewBelow": () => {
      runCell();
      actions.moveToNextCell({ cellId, before: false });
    },
    "cell.runAndNewAbove": () => {
      runCell();
      actions.moveToNextCell({ cellId, before: true });
    },
    "cell.createAbove": () => actions.createNewCell({ cellId, before: true }),
    "cell.createBelow": () => actions.createNewCell({ cellId, before: false }),
    "cell.moveUp": () => actions.moveCell({ cellId, before: true }),
    "cell.moveDown": () => actions.moveCell({ cellId, before: false }),
    "cell.moveLeft": () =>
      canMoveX ? actions.moveCell({ cellId, direction: "left" }) : undefined,
    "cell.moveRight": () =>
      canMoveX ? actions.moveCell({ cellId, direction: "right" }) : undefined,
    "cell.hideCode": () => {
      const nextHideCode = !cellConfig.hide_code;
      // Fire-and-forget
      void saveCellConfig({
        configs: { [cellId]: { hide_code: nextHideCode } },
      });
      actions.updateCellConfig({ cellId, config: { hide_code: nextHideCode } });
      if (nextHideCode) {
        // Move focus from the editor to the cell
        editorView.current?.contentDOM.blur();
        cellRef?.current?.focus();
      } else {
        // Focus the editor
        editorView.current?.focus();
      }
    },
    "cell.focusDown": () => actions.moveToNextCell({ cellId, before: false }),
    "cell.focusUp": () => actions.moveToNextCell({ cellId, before: true }),
    "cell.sendToBottom": () => actions.sendToBottom({ cellId }),
    "cell.sendToTop": () => actions.sendToTop({ cellId }),
    "cell.aiCompletion": () => {
      let closed = false;
      setAiCompletionCell((v) => {
        // Toggle close
        if (v?.cellId === cellId) {
          closed = true;
          return null;
        }
        return { cellId };
      });
      if (closed) {
        derefNotNull(editorView).focus();
      }
    },
    "cell.cellActions": () => {
      cellActionDropdownRef.current?.toggle();
    },
  });
}

/**
 * Hook for handling cell keyboard listeners
 */
function useCellKeyboardListener(
  cellRef: React.RefObject<HTMLDivElement> | null,
  cellId: CellId,
  actions: CellComponentActions,
  showHiddenMarkdownCode: () => void,
  userConfig: UserConfig,
  isCellCodeShown: boolean,
) {
  useKeydownOnElement(cellRef, {
    ArrowDown: (evt) => {
      if (evt && Events.fromInput(evt)) {
        return false;
      }
      actions.moveToNextCell({ cellId, before: false, noCreate: true });
      return true;
    },
    ArrowUp: (evt) => {
      if (evt && Events.fromInput(evt)) {
        return false;
      }
      actions.moveToNextCell({ cellId, before: true, noCreate: true });
      return true;
    },
    Enter: () => {
      showHiddenMarkdownCode();
      return false;
    },
    // only register j/k movement if the cell is hidden, so as to not
    // interfere with editing
    ...(userConfig.keymap.preset === "vim" && !isCellCodeShown
      ? {
          j: (evt) => {
            if (evt && Events.fromInput(evt)) {
              return false;
            }
            actions.moveToNextCell({ cellId, before: false, noCreate: true });
            return true;
          },
          k: (evt) => {
            if (evt && Events.fromInput(evt)) {
              return false;
            }
            actions.moveToNextCell({ cellId, before: true, noCreate: true });
            return true;
          },
        }
      : {}),
  });
}

/**
 * Hook for handling hidden cell logic
 */
function useCellHiddenLogic(
  cellConfig: CellConfig,
  languageAdapter: LanguageAdapterType | undefined,
  editorView: React.RefObject<EditorView | null>,
  editorViewParentRef: React.RefObject<HTMLDivElement>,
) {
  const [temporarilyVisible, setTemporarilyVisible] = useState(false);

  // The cell code is shown if the cell is not configured to be hidden or if the code is temporarily visible (i.e. when focused).
  const isCellCodeShown = !cellConfig.hide_code || temporarilyVisible;
  const isMarkdown = languageAdapter === "markdown";
  const isMarkdownCodeHidden = isMarkdown && !isCellCodeShown;

  // Callback to show the code editor temporarily
  const temporarilyShowCode = useCallback(() => {
    if (!isCellCodeShown) {
      setTemporarilyVisible(true);
      editorView.current?.focus();
      // Reach one parent up
      const parent = editorViewParentRef.current?.parentElement;
      if (!parent) {
        Logger.error("Cell: No parent element found for editor view");
        return;
      }

      const handleFocusOut = () => {
        requestAnimationFrame(() => {
          if (!parent.contains(document.activeElement)) {
            // Hide the code editor
            setTemporarilyVisible(false);
            editorView.current?.dom.blur();
            parent.removeEventListener("focusout", handleFocusOut);
          }
        });
      };
      parent.addEventListener("focusout", handleFocusOut);
    }
  }, [isCellCodeShown, editorView, editorViewParentRef, setTemporarilyVisible]);

  const showHiddenMarkdownCode = useCallback(() => {
    if (isMarkdownCodeHidden) {
      temporarilyShowCode();
    }
  }, [isMarkdownCodeHidden, temporarilyShowCode]);

  return {
    isCellCodeShown,
    isMarkdown,
    isMarkdownCodeHidden,
    temporarilyShowCode,
    showHiddenMarkdownCode,
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
  appClosed: boolean;
  /**
   * False only when there is only one cell in the notebook.
   */
  canDelete: boolean;
  /**
   * If true, the cell is allowed to be focus on.
   * This is false when the app is initially loading.
   */
  allowFocus: boolean;
  userConfig: UserConfig;
  canMoveX: boolean;
  isCollapsed: boolean;
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
    }),
    [editorView],
  );

  const outputStale = outputIsStale(
    { status, output, runStartTimestamp, interrupted, staleInputs },
    edited,
  );

  if (mode === "edit") {
    return (
      <EditableCellComponent
        {...props}
        editorView={editorView}
        setEditorView={(ev) => {
          editorView.current = ev;
        }}
        outputStale={outputStale}
      />
    );
  }

  return <ReadonlyCellComponent {...props} outputStale={outputStale} />;
};

const ReadonlyCellComponent = forwardRef(
  (
    props: Pick<
      CellProps,
      "id" | "output" | "interrupted" | "errored" | "stopped" | "name"
    > & {
      outputStale: boolean;
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
    } = props;

    const className = clsx("marimo-cell", "hover-actions-parent z-10", {
      published: true,
    });

    const HTMLId = HTMLCellId.create(cellId);

    const outputIsError = isErrorMime(output?.mimetype);

    // Hide the output if it's an error or stopped.
    const hidden = errored || interrupted || stopped || outputIsError;
    if (hidden) {
      return null;
    }

    return (
      <div
        tabIndex={-1}
        id={HTMLId}
        ref={ref}
        className={className}
        data-cell-id={cellId}
        data-cell-name={name}
      >
        <OutputArea
          allowExpand={false}
          forceExpand={true}
          output={output}
          className="output-area"
          cellId={cellId}
          stale={outputStale}
        />
      </div>
    );
  },
);
ReadonlyCellComponent.displayName = "ReadonlyCellComponent";

const EditableCellComponent = ({
  theme,
  showPlaceholder,
  allowFocus,
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
  appClosed,
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
  editorView: React.RefObject<EditorView>;
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
  const loading = status === "running" || status === "queued";

  // console output is cleared immediately on run, so check for queued instead
  // of loading to determine staleness
  const consoleOutputStale =
    (status === "queued" || edited || staleInputs) && !interrupted;

  // Callback to get the editor view.
  const getEditorView = useCallback(() => editorView.current, [editorView]);

  const createBelow = useEvent((opts: { code?: string } = {}) =>
    actions.createNewCell({ cellId, before: false, ...opts }),
  );
  const createAbove = useEvent((opts: { code?: string } = {}) =>
    actions.createNewCell({ cellId, before: true, ...opts }),
  );

  // Use the extracted hooks
  const { closeCompletionHandler, resumeCompletionHandler } = useCellCompletion(
    cellRef,
    editorView,
  );

  const {
    isCellCodeShown,
    isMarkdown,
    isMarkdownCodeHidden,
    temporarilyShowCode,
    showHiddenMarkdownCode,
  } = useCellHiddenLogic(
    cellConfig,
    languageAdapter,
    editorView,
    editorViewParentRef,
  );

  // Hotkey listeners
  useCellHotkeys(
    cellRef,
    cellId,
    runCell,
    actions,
    canMoveX,
    cellConfig,
    editorView,
    setAiCompletionCell,
    cellActionDropdownRef,
  );

  // Other keyboard listeners
  useCellKeyboardListener(
    cellRef,
    cellId,
    actions,
    showHiddenMarkdownCode,
    userConfig,
    isCellCodeShown,
  );

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
      onClick={temporarilyShowCode}
    />
  );

  const outputArea = hasOutput && (
    <div className="relative" onDoubleClick={showHiddenMarkdownCode}>
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
    borderless: isMarkdownCodeHidden && hasOutput,
  });

  const HTMLId = HTMLCellId.create(cellId);

  const handleRefactorWithAI = useEvent((opts: { prompt: string }) => {
    setAiCompletionCell({ cellId, initialPrompt: opts.prompt });
  });

  // TODO(akshayka): Move to our own Tooltip component once it's easier
  // to get the tooltip to show next to the cursor ...
  // https://github.com/radix-ui/primitives/discussions/1090
  const cellTitle = () => {
    if (cellConfig.disabled) {
      return "This cell is disabled";
    }
    if (status === "disabled-transitively") {
      return "This cell has a disabled ancestor";
    }
    return undefined;
  };

  const cellStatusComponent = (
    <CellStatusComponent
      status={status}
      staleInputs={staleInputs}
      interrupted={interrupted}
      editing={true}
      edited={edited}
      disabled={cellConfig.disabled ?? false}
      elapsedTime={runElapsedTimeMs}
      runStartTimestamp={runStartTimestamp}
      uninstantiated={uninstantiated}
      lastRunStartTimestamp={lastRunStartTimestamp}
    />
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
          title={cellTitle()}
        >
          <div
            className={className}
            id={HTMLId}
            ref={cellContainerRef}
            data-cell-id={cellId}
            data-cell-name={name}
          >
            {cellOutput === "above" && outputArea}
            <div className={cn("tray")} data-hidden={isMarkdownCodeHidden}>
              <div className="absolute right-2 -top-4 z-10">
                <CellToolbar
                  edited={edited}
                  appClosed={appClosed}
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
              <div
                className={cn(
                  "absolute flex flex-col gap-[2px] justify-center h-full left-[-34px] z-20",
                  isMarkdownCodeHidden && hasOutputAbove && "-top-7",
                  isMarkdownCodeHidden && hasOutputBelow && "-bottom-8",
                  isMarkdownCodeHidden &&
                    isCellButtonsInline &&
                    "-left-[3.8rem]",
                )}
              >
                <CreateCellButton
                  tooltipContent={renderShortcut("cell.createAbove")}
                  appClosed={appClosed}
                  onClick={appClosed ? undefined : createAbove}
                />
                <div className="flex-1" />
                <CreateCellButton
                  tooltipContent={renderShortcut("cell.createBelow")}
                  appClosed={appClosed}
                  onClick={appClosed ? undefined : createBelow}
                />
              </div>
              <CellEditor
                theme={theme}
                showPlaceholder={showPlaceholder}
                allowFocus={allowFocus}
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
                temporarilyShowCode={temporarilyShowCode}
                languageAdapter={languageAdapter}
                setLanguageAdapter={setLanguageAdapter}
              />
              <div
                className={cn(
                  "shoulder-right z-20",
                  isMarkdownCodeHidden && cellOutput === "below" && "top-14",
                )}
              >
                {!isCellStatusInline && cellStatusComponent}
                <div className="flex gap-2 items-end">
                  <CellDragHandle />
                  {isCellStatusInline && cellStatusComponent}
                </div>
              </div>
              <div className="shoulder-bottom hover-action">
                {canDelete && isCellCodeShown && (
                  <DeleteButton
                    appClosed={appClosed}
                    status={status}
                    onClick={() => {
                      if (!loading && !appClosed) {
                        deleteCell({ cellId });
                      }
                    }}
                  />
                )}
              </div>
            </div>
            {cellOutput === "below" && outputArea}
            <ConsoleOutput
              consoleOutputs={consoleOutputs}
              stale={consoleOutputStale}
              cellName={name}
              onRefactorWithAI={handleRefactorWithAI}
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

interface CellToolbarProps {
  edited: boolean;
  appClosed: boolean;
  status: RuntimeState;
  cellConfig: CellConfig;
  needsRun: boolean;
  hasOutput: boolean;
  hasConsoleOutput: boolean;
  cellActionDropdownRef: React.RefObject<CellActionsDropdownHandle>;
  cellId: CellId;
  name: string;
  getEditorView: () => EditorView | null;
  onRun: () => void;
}

const CellToolbar = ({
  edited,
  appClosed,
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
}: CellToolbarProps) => {
  return (
    <Toolbar
      className={cn(
        // Show the toolbar on hover, or when the cell needs to be run
        !needsRun && "hover-action",
      )}
    >
      <RunButton
        edited={edited}
        onClick={appClosed ? Functions.NOOP : onRun}
        appClosed={appClosed}
        status={status}
        config={cellConfig}
        needsRun={needsRun}
      />
      <StopButton status={status} appClosed={appClosed} />
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
    </Toolbar>
  );
};

export const Cell = memo(forwardRef<CellHandle, CellProps>(CellComponent));
