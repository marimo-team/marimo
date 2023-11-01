/* Copyright 2023 Marimo. All rights reserved. */
import { closeCompletion, completionStatus } from "@codemirror/autocomplete";
import { historyField } from "@codemirror/commands";
import { EditorState, StateEffect } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import {
  memo,
  FocusEvent,
  KeyboardEvent,
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useLayoutEffect,
} from "react";

import { sendRun } from "@/core/network/requests";
import { autocompletionKeymap, setupCodeMirror } from "@/core/codemirror/cm";

import { UserConfig } from "../core/config/config";
import { CellData, CellRuntimeState } from "../core/model/cells";
import { CellActions, useCellActions } from "../core/state/cells";
import { derefNotNull } from "../utils/dereference";
import { OutputArea } from "./Output";
import { ConsoleOutput } from "./output/ConsoleOutput";
import { CreateCellButton } from "./cell/CreateCellButton";
import { RunButton } from "./cell/RunButton";
import { DeleteButton } from "./cell/DeleteButton";
import { CellStatusComponent } from "./cell/CellStatus";
import clsx from "clsx";
import { renderShortcut } from "../components/shortcuts/renderShortcut";
import { useCellRenderCount } from "../hooks/useCellRenderCount";
import { Functions } from "../utils/functions";
import { Logger } from "../utils/Logger";
import { SerializedEditorState } from "../core/codemirror/types";
import { CellDragHandle, SortableCell } from "./SortableCell";
import { HTMLCellId } from "../core/model/ids";
import { Theme } from "../theme/useTheme";
import { CellActionsDropdown } from "./cell/cell-actions";
import { CellActionsContextMenu } from "./cell/cell-context-menu";
import { AppMode } from "@/core/mode";
import useEvent from "react-use-event-hook";

/**
 * Imperative interface of the cell.
 */
export interface CellHandle {
  /**
   * The CodeMirror editor view.
   */
  editorView: EditorView;
  /**
   * Get the serialized editor state.
   */
  editorStateJSON: () => Record<string, unknown>;
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
    >,
    Pick<CellData, "id" | "code" | "edited" | "config">,
    Pick<
      CellActions,
      | "updateCellCode"
      | "prepareForRun"
      | "createNewCell"
      | "deleteCell"
      | "focusCell"
      | "moveCell"
      | "moveToNextCell"
    > {
  theme: Theme;
  showPlaceholder: boolean;
  registerRunStart: () => void;
  serializedEditorState: SerializedEditorState | null;
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
    registerRunStart,
    serializedEditorState,
    mode,
    appClosed,
    showDeleteButton,
    updateCellCode,
    prepareForRun,
    createNewCell,
    deleteCell,
    focusCell,
    moveCell,
    moveToNextCell,
    userConfig,
    config: cellConfig,
  }: CellProps,
  ref: React.ForwardedRef<CellHandle>
) => {
  useCellRenderCount().countRender();

  Logger.debug("Rendering Cell", cellId);
  const cellRef = useRef<HTMLDivElement>(null);
  const editorView = useRef<EditorView | null>(null);
  // DOM node where the editorView will be mounted
  const editorViewParentRef = useRef<HTMLDivElement>(null);

  const needsRun = edited || interrupted;
  const loading = status === "running" || status === "queued";
  // output may or may not be refreshed while a cell is running, so
  // we need to check if an output was received
  const outputReceivedWhileRunning =
    status === "running" &&
    output !== null &&
    runStartTimestamp !== null &&
    output.timestamp > runStartTimestamp;
  const outputStale =
    ((loading && !outputReceivedWhileRunning) ||
      edited ||
      status === "stale") &&
    !interrupted;
  // console output is cleared immediately on run, so check for queued instead
  // of loading to determine staleness
  const consoleOutputStale =
    (status === "queued" || edited || status === "stale") && !interrupted;
  const editing = mode === "edit";
  const reading = mode === "read";
  const { sendToTop, sendToBottom } = useCellActions();

  // Performs side-effects that must run whenever the cell is run, but doesn't
  // actually run the cell.
  //
  // Returns the code to run.
  const prepareToRunEffects = useCallback(() => {
    const code = derefNotNull(editorView).state.doc.toString();
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
      editorStateJSON: () => {
        return derefNotNull(editorView).state.toJSON({ history: historyField });
      },
      registerRun: prepareToRunEffects,
    }),
    [editorView, prepareToRunEffects]
  );

  const handleRun = useEvent(() => {
    if (loading) {
      return;
    }

    const code = prepareToRunEffects();
    registerRunStart();
    sendRun(cellId, code);
  });

  const handleDelete = useEvent(() => {
    // Cannot delete running cells, since we're waiting for their output.
    if (loading) {
      return false;
    }

    deleteCell({ cellId });
    return true;
  });

  const createBelow = useCallback(
    () => createNewCell({ cellId, before: false }),
    [cellId, createNewCell]
  );
  const createAbove = useCallback(
    () => createNewCell({ cellId, before: true }),
    [cellId, createNewCell]
  );
  const moveDown = useCallback(
    () => moveCell({ cellId, before: false }),
    [cellId, moveCell]
  );
  const moveUp = useCallback(
    () => moveCell({ cellId, before: true }),
    [cellId, moveCell]
  );
  const focusDown = useCallback(
    () => focusCell({ cellId, before: false }),
    [cellId, focusCell]
  );
  const focusUp = useCallback(
    () => focusCell({ cellId, before: true }),
    [cellId, focusCell]
  );

  useEffect(() => {
    if (reading) {
      return;
    }

    const extensions = setupCodeMirror({
      cellId,
      showPlaceholder,
      cellCodeCallbacks: {
        updateCellCode,
      },
      cellMovementCallbacks: {
        onRun: handleRun,
        deleteCell: handleDelete,
        createAbove,
        createBelow,
        moveUp,
        moveDown,
        focusUp,
        focusDown,
        sendToTop,
        sendToBottom,
        moveToNextCell,
      },
      completionConfig: userConfig.completion,
      keymapConfig: userConfig.keymap,
      theme,
    });

    // Should focus will be true if its a newly created editor
    let shouldFocus: boolean;
    if (serializedEditorState === null) {
      // If the editor already exists, reconfigure it with the new extensions.
      // Triggered when, e.g., placeholder changes.
      if (editorView.current === null) {
        // Otherwise, create a new editor.
        editorView.current = new EditorView({
          state: EditorState.create({
            doc: code,
            extensions: extensions,
          }),
        });
        shouldFocus = true;
      } else {
        editorView.current.dispatch({
          effects: [StateEffect.reconfigure.of([extensions])],
        });
        shouldFocus = false;
      }
    } else {
      editorView.current = new EditorView({
        state: EditorState.fromJSON(
          serializedEditorState,
          {
            doc: code,
            extensions: extensions,
          },
          { history: historyField }
        ),
      });
      shouldFocus = true;
    }

    if (editorView.current !== null && editorViewParentRef.current !== null) {
      // Always replace the children in case the editor view was re-created.
      editorViewParentRef.current.replaceChildren(editorView.current.dom);
    }

    if (shouldFocus && allowFocus) {
      // Focus and scroll into view; request an animation frame to
      // avoid a race condition when new editors are created
      // very rapidly by holding a hotkey
      requestAnimationFrame(() => {
        editorView.current?.focus();
        editorView.current?.dom.scrollIntoView({
          behavior: "smooth",
          block: "center",
        });
      });
    }

    // We don't want to re-run this effect when `allowFocus` or `code` changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    reading,
    cellId,
    userConfig.completion.activate_on_typing,
    userConfig.keymap,
    theme,
    showPlaceholder,
    createAbove,
    createBelow,
    focusUp,
    focusDown,
    moveUp,
    moveDown,
    moveToNextCell,
    updateCellCode,
    handleDelete,
    handleRun,
    serializedEditorState,
  ]);

  useLayoutEffect(() => {
    if (editorView.current === null) {
      return;
    }
    if (
      editing &&
      editorViewParentRef.current !== null &&
      editorView.current !== null
    ) {
      editorViewParentRef.current.replaceChildren(editorView.current.dom);
    }
  }, [editing]);

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
      output={output}
      className="output-area"
      cellId={cellId}
      stale={outputStale}
    />
  );

  const className = clsx("Cell", "hover-actions-parent", {
    published: !editing,
    "needs-run": needsRun,
    "has-error": errored,
    stopped: stopped,
    disabled: cellConfig.disabled,
    stale: status === "stale" || status === "disabled-transitively",
  });

  const HTMLId = HTMLCellId.create(cellId);
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

  const editor = <div className="cm" ref={editorViewParentRef} />;

  return (
    <CellActionsContextMenu
      cellId={cellId}
      config={cellConfig}
      status={status}
      editorView={editorView.current}
      hasOutput={!!output}
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
        {outputArea}
        <div className="tray">
          <div className="shoulder-left hover-action">
            <div className="shoulder-elem-top">
              <CreateCellButton
                tooltipContent={renderShortcut("cell.createAbove")}
                appClosed={appClosed}
                onClick={appClosed ? undefined : createAbove}
              />
            </div>
            <div className="shoulder-elem-bottom">
              <CreateCellButton
                tooltipContent={renderShortcut("cell.createBelow")}
                appClosed={appClosed}
                onClick={appClosed ? undefined : createBelow}
              />
            </div>
          </div>
          {editor}
          <div className="shoulder-right">
            <CellStatusComponent
              status={status}
              interrupted={interrupted}
              editing={editing}
              edited={edited}
              disabled={cellConfig.disabled ?? false}
              elapsedTime={runElapsedTimeMs}
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
                config={cellConfig}
                hasOutput={!!output}
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
        <ConsoleOutput
          consoleOutputs={consoleOutputs}
          stale={consoleOutputStale}
        />
      </SortableCell>
    </CellActionsContextMenu>
  );
};

export const Cell = memo(forwardRef<CellHandle, CellProps>(CellComponent));
