/* Copyright 2024 Marimo. All rights reserved. */
import { closeCompletion, completionStatus } from "@codemirror/autocomplete";
import { EditorView } from "@codemirror/view";
import {
  memo,
  FocusEvent,
  KeyboardEvent,
  forwardRef,
  useCallback,
  useImperativeHandle,
  useRef,
} from "react";

import { saveCellConfig, sendRun, sendStdin } from "@/core/network/requests";
import { autocompletionKeymap } from "@/core/codemirror/cm";
import { UserConfig } from "../../core/config/config-schema";
import { CellConfig, CellData, CellRuntimeState } from "../../core/cells/types";
import { CellActions } from "../../core/cells/cells";
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
import { HTMLCellId } from "../../core/cells/ids";
import { Theme } from "../../theme/useTheme";
import { CellActionsDropdown } from "./cell/cell-actions";
import { CellActionsContextMenu } from "./cell/cell-context-menu";
import { AppMode } from "@/core/mode";
import useEvent from "react-use-event-hook";
import { CellEditor } from "./cell/code/cell-editor";
import { getEditorCodeAsPython } from "@/core/codemirror/language/utils";
import { outputIsStale } from "@/core/cells/cell";
import { RuntimeState } from "@/core/kernel/RuntimeState";
import { isOutputEmpty } from "@/core/cells/outputs";
import { useHotkeysOnElement, useKeydownOnElement } from "@/hooks/useHotkey";

/**
 * Imperative interface of the cell.
 */
export interface CellHandle {
  /**
   * The CodeMirror editor view.
   */
  editorView: EditorView;
  /**
   * Register the cell to run.
   */
  registerRun: () => void;
}

export interface CellProps
  extends Pick<
      CellRuntimeState,
      | "consoleOutputs"
      | "status"
      | "output"
      | "errored"
      | "interrupted"
      | "stopped"
      | "runStartTimestamp"
      | "runElapsedTimeMs"
      | "debuggerActive"
    >,
    Pick<
      CellData,
      "id" | "code" | "edited" | "config" | "name" | "serializedEditorState"
    >,
    Pick<
      CellActions,
      | "updateCellCode"
      | "prepareForRun"
      | "createNewCell"
      | "deleteCell"
      | "focusCell"
      | "moveCell"
      | "moveToNextCell"
      | "updateCellConfig"
      | "setStdinResponse"
      | "sendToBottom"
      | "sendToTop"
    > {
  theme: Theme;
  showPlaceholder: boolean;
  mode: AppMode;
  appClosed: boolean;
  showDeleteButton: boolean;
  /**
   * If true, the cell is allowed to be focus on.
   * This is false when the app is initially loading.
   */
  allowFocus: boolean;
  userConfig: UserConfig;
}

// TODO(akshayka): a component for displaying/editing the cell's name.
const CellComponent = (
  {
    theme,
    showPlaceholder,
    allowFocus,
    id: cellId,
    code,
    output,
    consoleOutputs,
    status,
    runStartTimestamp,
    runElapsedTimeMs,
    edited,
    interrupted,
    errored,
    stopped,
    serializedEditorState,
    mode,
    debuggerActive,
    appClosed,
    showDeleteButton,
    updateCellCode,
    prepareForRun,
    createNewCell,
    deleteCell,
    focusCell,
    moveCell,
    setStdinResponse,
    moveToNextCell,
    updateCellConfig,
    sendToBottom,
    sendToTop,
    userConfig,
    config: cellConfig,
    name,
  }: CellProps,
  ref: React.ForwardedRef<CellHandle>
) => {
  useCellRenderCount().countRender();

  Logger.debug("Rendering Cell", cellId);
  const cellRef = useRef<HTMLDivElement>(null);
  const editorView = useRef<EditorView | null>(null);

  const needsRun = edited || interrupted;
  const loading = status === "running" || status === "queued";
  const outputStale = outputIsStale(
    { status, output, runStartTimestamp, interrupted },
    edited
  );

  // console output is cleared immediately on run, so check for queued instead
  // of loading to determine staleness
  const consoleOutputStale =
    (status === "queued" || edited || status === "stale") && !interrupted;
  const editing = mode === "edit";

  // Performs side-effects that must run whenever the cell is run, but doesn't
  // actually run the cell.
  //
  // Returns the code to run.
  const prepareToRunEffects = useCallback(() => {
    const code = getEditorCodeAsPython(derefNotNull(editorView));
    closeCompletion(derefNotNull(editorView));
    prepareForRun({ cellId });
    return code;
  }, [cellId, editorView, prepareForRun]);

  // An imperative interface to the code editor
  useImperativeHandle(
    ref,
    () => ({
      get editorView() {
        return derefNotNull(editorView);
      },
      registerRun: prepareToRunEffects,
    }),
    [editorView, prepareToRunEffects]
  );

  const handleRun = useEvent(async () => {
    if (loading) {
      return;
    }

    const code = prepareToRunEffects();

    RuntimeState.INSTANCE.registerRunStart();
    await sendRun([cellId], [code]).catch((error) => {
      Logger.error("Error running cell", error);
      RuntimeState.INSTANCE.registerRunEnd();
    });
  });

  const createBelow = useCallback(
    () => createNewCell({ cellId, before: false }),
    [cellId, createNewCell]
  );
  const createAbove = useCallback(
    () => createNewCell({ cellId, before: true }),
    [cellId, createNewCell]
  );

  // Close completion when focus leaves the cell's subtree.
  const closeCompletionHandler = useCallback((e: FocusEvent) => {
    if (
      cellRef.current !== null &&
      !cellRef.current.contains(e.relatedTarget) &&
      editorView.current !== null
    ) {
      closeCompletion(editorView.current);
    }
  }, []);

  // Clicking on the completion info causes the editor view to lose focus,
  // because the completion is not a child of the editable editor DOM;
  // as a workaround, when a completion is active, we refocus the editor
  // on any keypress.
  //
  // See https://discuss.codemirror.net/t/adding-click-event-listener-to-autocomplete-tooltip-info-panel-is-not-working/4741
  const resumeCompletionHandler = useCallback(
    (e: KeyboardEvent) => {
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
    },
    [cellRef, editorView]
  );

  const outputArea = (
    <OutputArea
      allowExpand={editing}
      output={output}
      className="output-area"
      cellId={cellId}
      stale={outputStale}
    />
  );

  const className = clsx("Cell", "hover-actions-parent", {
    published: !editing,
    interactive: editing,
    "needs-run": needsRun,
    "has-error": errored,
    stopped: stopped,
    disabled: cellConfig.disabled,
    stale: status === "stale" || status === "disabled-transitively",
  });

  const HTMLId = HTMLCellId.create(cellId);

  // Register hotkeys on the cell instead of the code editor
  // This is in case the code editor is hidden
  useHotkeysOnElement(editing ? cellRef.current : null, {
    "cell.run": handleRun,
    "cell.runAndNewBelow": () => {
      handleRun();
      moveToNextCell({ cellId, before: false });
    },
    "cell.runAndNewAbove": () => {
      handleRun();
      moveToNextCell({ cellId, before: true });
    },
    "cell.createAbove": createAbove,
    "cell.createBelow": createBelow,
    "cell.moveUp": () => moveCell({ cellId, before: true }),
    "cell.moveDown": () => moveCell({ cellId, before: false }),
    "cell.hideCode": () => {
      const newConfig: CellConfig = { hide_code: !cellConfig.hide_code };
      // Fire-and-forget
      void saveCellConfig({ configs: { [cellId]: newConfig } });
      updateCellConfig({ cellId, config: newConfig });
      if (newConfig.hide_code) {
        // Move focus from the editor to the cell
        editorView.current?.contentDOM.blur();
        cellRef.current?.focus();
      } else {
        // Focus the editor
        editorView.current?.focus();
      }
    },
    "cell.focusDown": () => moveToNextCell({ cellId, before: false }),
    "cell.focusUp": () => moveToNextCell({ cellId, before: true }),
    "cell.sendToBottom": () => sendToBottom({ cellId }),
    "cell.sendToTop": () => sendToTop({ cellId }),
  });

  useKeydownOnElement(editing ? cellRef.current : null, {
    ArrowDown: () => {
      moveToNextCell({ cellId, before: false, noCreate: true });
      return true;
    },
    ArrowUp: () => {
      moveToNextCell({ cellId, before: true, noCreate: true });
      return true;
    },
    // only register j/k movement if the cell is hidden, so as to not
    // interfere with editing
    ...(userConfig.keymap.preset === "vim" && cellConfig.hide_code
      ? {
          j: () => {
            moveToNextCell({ cellId, before: false, noCreate: true });
            return true;
          },
          k: () => {
            moveToNextCell({ cellId, before: true, noCreate: true });
            return true;
          },
        }
      : {}),
  });

  if (!editing) {
    const hidden = errored || interrupted || stopped;
    return hidden ? null : (
      <div tabIndex={-1} id={HTMLId} ref={cellRef} className={className}>
        {outputArea}
      </div>
    );
  }

  // TODO(akshayka): Move to our own Tooltip component once it's easier
  // to get the tooltip to show next to the cursor ...
  // https://github.com/radix-ui/primitives/discussions/1090
  const cellTitle = () => {
    if (cellConfig.disabled) {
      return "This cell is disabled";
    } else if (status === "stale" || status === "disabled-transitively") {
      return "This cell has a disabled ancestor";
    } else {
      return undefined;
    }
  };

  const hasOutput = !isOutputEmpty(output);

  return (
    <CellActionsContextMenu
      cellId={cellId}
      config={cellConfig}
      status={status}
      editorView={editorView.current}
      hasOutput={hasOutput}
      name={name}
    >
      <SortableCell
        tabIndex={-1}
        id={HTMLId}
        ref={cellRef}
        className={className}
        data-status={status}
        onBlur={closeCompletionHandler}
        onKeyDown={resumeCompletionHandler}
        cellId={cellId}
        title={cellTitle()}
      >
        {userConfig.display.cell_output === "above" && outputArea}
        <div className="tray">
          <div className="absolute flex flex-col gap-[2px] justify-center h-full left-[-34px] z-2 hover-action">
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
            status={status}
            serializedEditorState={serializedEditorState}
            mode={mode}
            runCell={handleRun}
            updateCellCode={updateCellCode}
            createNewCell={createNewCell}
            deleteCell={deleteCell}
            focusCell={focusCell}
            moveCell={moveCell}
            moveToNextCell={moveToNextCell}
            updateCellConfig={updateCellConfig}
            userConfig={userConfig}
            editorViewRef={editorView}
            hidden={cellConfig.hide_code}
          />
          <div className="shoulder-right">
            <CellStatusComponent
              status={status}
              interrupted={interrupted}
              editing={editing}
              edited={edited}
              disabled={cellConfig.disabled ?? false}
              elapsedTime={runElapsedTimeMs}
              runStartTimestamp={runStartTimestamp}
            />
            <div className="flex align-bottom">
              <RunButton
                edited={edited}
                onClick={appClosed ? Functions.NOOP : handleRun}
                appClosed={appClosed}
                status={status}
                config={cellConfig}
                needsRun={needsRun}
              />
              <CellActionsDropdown
                cellId={cellId}
                status={status}
                editorView={editorView.current}
                name={name}
                config={cellConfig}
                hasOutput={hasOutput}
              >
                <CellDragHandle />
              </CellActionsDropdown>
            </div>
          </div>
          <div className="shoulder-bottom hover-action">
            {showDeleteButton ? (
              <DeleteButton
                appClosed={appClosed}
                status={status}
                onClick={() => {
                  if (!loading && !appClosed) {
                    deleteCell({ cellId });
                  }
                }}
              />
            ) : null}
          </div>
        </div>
        {userConfig.display.cell_output === "below" && outputArea}
        <ConsoleOutput
          consoleOutputs={consoleOutputs}
          stale={consoleOutputStale}
          cellName={name}
          onSubmitDebugger={(text, index) => {
            setStdinResponse({ cellId, response: text, outputIndex: index });
            sendStdin({ text });
          }}
          cellId={cellId}
          debuggerActive={debuggerActive}
        />
      </SortableCell>
    </CellActionsContextMenu>
  );
};

export const Cell = memo(forwardRef<CellHandle, CellProps>(CellComponent));
