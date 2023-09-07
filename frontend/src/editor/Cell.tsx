/* Copyright 2023 Marimo. All rights reserved. */
import { closeCompletion, completionStatus } from "@codemirror/autocomplete";
import { historyField } from "@codemirror/commands";
import { foldAll, unfoldAll } from "@codemirror/language";
import { EditorState, Prec, StateEffect } from "@codemirror/state";
import { keymap, EditorView, KeyBinding } from "@codemirror/view";
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
import { autocompletionKeymap, setup } from "@/core/codemirror/cm";

import { UserConfig } from "../core/config";
import { CellState } from "../core/model/cells";
import { CellActions, useCellActions } from "../core/state/cells";
import { derefNotNull } from "../utils/dereference";
import { ConsoleOutputArea, OutputArea } from "./Output";
import { CreateCellButton } from "./cell/CreateCellButton";
import { RunButton } from "./cell/RunButton";
import { DeleteButton } from "./cell/DeleteButton";
import { CellStatusComponent } from "./cell/CellStatus";
import clsx from "clsx";
import { renderShortcut } from "../components/shortcuts/renderShortcut";
import {
  formatKeymapExtension,
  scrollActiveLineIntoView,
  smartPlaceholderExtension,
} from "../core/codemirror/extensions";
import { useCellRenderCount } from "../hooks/useCellRenderCount";
import { Functions } from "../utils/functions";
import { Logger } from "../utils/Logger";
import { SerializedEditorState } from "../core/codemirror/types";
import { CellDragHandle, SortableCell } from "./SortableCell";
import { CellId, HTMLCellId } from "../core/model/ids";
import { Theme } from "../theme/useTheme";
import { HOTKEYS } from "@/core/hotkeys/hotkeys";
import { keymapBundle } from "@/core/codemirror/keymaps/keymaps";
import { CellActionsDropdown } from "./cell/cell-actions";

/**
 * Imperative interface of the cell.
 */
export interface CellHandle {
  /**
   * The CodeMirror editor view.
   */
  editorView: EditorView;
  /**
   * Folds all code in the editor.
   */
  foldAll: () => boolean;
  /**
   * Unfolds all code in the editor.
   */
  unfoldAll: () => boolean;
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
      CellState,
      | "consoleOutputs"
      | "status"
      | "output"
      | "initialContents"
      | "edited"
      | "errored"
      | "interrupted"
      | "config"
      | "stopped"
      | "runElapsedTimeMs"
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
    > {
  theme: Theme;
  showPlaceholder: boolean;
  cellId: CellId;
  registerRunStart: () => void;
  serializedEditorState: SerializedEditorState | null;
  editing: boolean;
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
    cellId,
    initialContents,
    output,
    consoleOutputs,
    status,
    runElapsedTimeMs,
    edited,
    interrupted,
    errored,
    stopped,
    registerRunStart,
    serializedEditorState,
    editing,
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
  const runningOrQueuedRef = useRef<boolean | null>(null);

  const needsRun = edited || interrupted;
  const loading = status === "running" || status === "queued";
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
      foldAll() {
        if (editorView.current !== null) {
          return foldAll(derefNotNull(editorView));
        }
        return false;
      },
      unfoldAll() {
        if (editorView.current !== null) {
          return unfoldAll(derefNotNull(editorView));
        }
        return false;
      },
      editorStateJSON: () => {
        return derefNotNull(editorView).state.toJSON({ history: historyField });
      },
      registerRun: prepareToRunEffects,
    }),
    [editorView, prepareToRunEffects]
  );

  // Hack to provide the value of `running` to Code Mirror's EditorView.
  useEffect(() => {
    runningOrQueuedRef.current = loading;
  }, [loading]);

  const onRun = useCallback(() => {
    if (!runningOrQueuedRef.current) {
      const code = prepareToRunEffects();
      registerRunStart();
      sendRun(cellId, code);
    }
  }, [cellId, registerRunStart, prepareToRunEffects]);

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
    const cellEditingHotkeys: KeyBinding[] = [
      {
        key: HOTKEYS.getHotkey("cell.run").key,
        preventDefault: true,
        run: () => {
          onRun();
          return true;
        },
      },
      {
        key: HOTKEYS.getHotkey("cell.runAndNewBelow").key,
        preventDefault: true,
        run: (ev) => {
          onRun();
          ev.contentDOM.blur();
          moveToNextCell({ cellId, before: false });
          return true;
        },
      },
      {
        key: HOTKEYS.getHotkey("cell.runAndNewAbove").key,
        preventDefault: true,
        run: (ev) => {
          onRun();
          ev.contentDOM.blur();
          moveToNextCell({ cellId, before: true });
          return true;
        },
      },
      {
        key: HOTKEYS.getHotkey("cell.delete").key,
        preventDefault: true,
        run: (cm) => {
          // Cannot delete running cells, since we're waiting for their output.
          // Cannot delete non-empty cells for safety
          if (!runningOrQueuedRef.current && cm.state.doc.length === 0) {
            deleteCell({ cellId });
          }
          // shortcuts.delete (shift-backspace) overlaps with
          // defaultKeymap's deleteCharBackward (backspace); we don't want
          // shift-backspace to trigger character deletion, because otherwise
          // users might accidentally delete their whole notebook if they
          // absent-mindedly held these keys. That's why we always return true.
          return true;
        },
      },
      {
        key: HOTKEYS.getHotkey("cell.moveDown").key,
        preventDefault: true,
        run: () => {
          moveDown();
          return true;
        },
      },
      {
        key: HOTKEYS.getHotkey("cell.moveUp").key,
        preventDefault: true,
        run: () => {
          moveUp();
          return true;
        },
      },
      {
        key: HOTKEYS.getHotkey("cell.focusDown").key,
        preventDefault: true,
        run: () => {
          focusDown();
          return true;
        },
      },
      {
        key: HOTKEYS.getHotkey("cell.focusUp").key,
        preventDefault: true,
        run: () => {
          focusUp();
          return true;
        },
      },
      {
        key: HOTKEYS.getHotkey("cell.sendToBottom").key,
        preventDefault: true,
        run: () => {
          sendToBottom({ cellId });
          return true;
        },
      },
      {
        key: HOTKEYS.getHotkey("cell.sendToTop").key,
        preventDefault: true,
        run: () => {
          sendToTop({ cellId });
          return true;
        },
      },
      {
        key: HOTKEYS.getHotkey("cell.createAbove").key,
        preventDefault: true,
        run: (ev) => {
          ev.contentDOM.blur();
          createAbove();
          return true;
        },
      },
      {
        key: HOTKEYS.getHotkey("cell.createBelow").key,
        preventDefault: true,
        run: (ev) => {
          ev.contentDOM.blur();
          createBelow();
          return true;
        },
      },
    ];

    const onChangePlugin = EditorView.updateListener.of((update) => {
      if (update.docChanged) {
        updateCellCode({
          cellId,
          code: update.state.doc.toString(),
          formattingChange: false,
        });
      }
    });

    const extensions = [
      // Our keymap goes first
      Prec.highest(keymap.of(cellEditingHotkeys)),
      Prec.highest(formatKeymapExtension(cellId, updateCellCode)),
      // Then editor keymaps (vim or defaults) based on user config
      keymapBundle(userConfig.keymap, {
        deleteCell: () => {
          // Cannot delete running cells, since we're waiting for their output.
          if (!runningOrQueuedRef.current) {
            deleteCell({ cellId });
          }
          return true;
        },
      }),
      // Default setup
      ...setup(userConfig.completion, theme),
      scrollActiveLineIntoView(),
      onChangePlugin,
      showPlaceholder
        ? Prec.highest(smartPlaceholderExtension("import marimo as mo"))
        : [],
    ];

    // Should focus will be true if its a newly created editor
    let shouldFocus: boolean;
    if (serializedEditorState === null) {
      // If the editor already exists, reconfigure it with the new extensions.
      // Triggered when, e.g., placeholder changes.
      if (editorView.current === null) {
        // Otherwise, create a new editor.
        editorView.current = new EditorView({
          state: EditorState.create({
            doc: initialContents,
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
            doc: initialContents,
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

    // We don't want to re-run this effect when `allowFocus` changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    cellId,
    userConfig.completion.activate_on_typing,
    userConfig.keymap,
    theme,
    showPlaceholder,
    initialContents,
    createAbove,
    createBelow,
    deleteCell,
    focusUp,
    focusDown,
    moveUp,
    moveDown,
    moveToNextCell,
    updateCellCode,
    onRun,
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
      cellId={cellId}
      stale={(loading || edited) && !interrupted}
    />
  );

  const className = clsx("Cell", "hover-actions-parent", {
    published: !editing,
    "needs-run": needsRun,
    "has-error": errored,
    stopped: stopped,
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

  const editor = <div className="cm" ref={editorViewParentRef} />;

  return (
    <SortableCell
      tabIndex={-1}
      id={HTMLId}
      ref={cellRef}
      className={className}
      onBlur={closeCompletionHandler}
      onKeyDown={resumeCompletionHandler}
      cellId={cellId}
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
            elapsedTime={runElapsedTimeMs}
          />
          <div className="flex align-bottom">
            <RunButton
              onClick={appClosed ? Functions.NOOP : onRun}
              appClosed={appClosed}
              status={status}
              needsRun={needsRun}
            />
            <CellActionsDropdown
              cellId={cellId}
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
      <ConsoleOutputArea
        consoleOutputs={consoleOutputs}
        cellId={cellId}
        stale={(status === "queued" || edited) && !interrupted}
      />
    </SortableCell>
  );
};

export const Cell = memo(forwardRef<CellHandle, CellProps>(CellComponent));
