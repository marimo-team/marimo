/* Copyright 2024 Marimo. All rights reserved. */
import { historyField } from "@codemirror/commands";
import { EditorState, StateEffect } from "@codemirror/state";
import { EditorView, ViewPlugin } from "@codemirror/view";
import {
  memo,
  useCallback,
  useEffect,
  useRef,
  useLayoutEffect,
  useState,
} from "react";

import { setupCodeMirror } from "@/core/codemirror/cm";
import { AppMode } from "@/core/mode";
import useEvent from "react-use-event-hook";
import { CellActions, useCellActions } from "@/core/cells/cells";
import { CellRuntimeState, CellData, CellConfig } from "@/core/cells/types";
import { UserConfig } from "@/core/config/config-schema";
import { Theme } from "@/theme/useTheme";
import {
  LanguageAdapters,
  languageAdapterState,
  reconfigureLanguageEffect,
} from "@/core/codemirror/language/extension";
import { derefNotNull } from "@/utils/dereference";
import { LanguageToggle } from "./language-toggle";
import { cn } from "@/utils/cn";
import { saveCellConfig } from "@/core/network/requests";
import { HideCodeButton } from "../../code/readonly-python-code";

export interface CellEditorProps
  extends Pick<CellRuntimeState, "status">,
    Pick<CellData, "id" | "code" | "serializedEditorState">,
    Pick<
      CellActions,
      | "updateCellCode"
      | "createNewCell"
      | "deleteCell"
      | "focusCell"
      | "moveCell"
      | "moveToNextCell"
      | "updateCellConfig"
    > {
  runCell: () => void;
  theme: Theme;
  showPlaceholder: boolean;
  mode: AppMode;
  editorViewRef: React.MutableRefObject<EditorView | null>;
  /**
   * If true, the cell is allowed to be focus on.
   * This is false when the app is initially loading.
   */
  allowFocus: boolean;
  userConfig: UserConfig;
  hidden?: boolean;
}

const CellEditorInternal = ({
  theme,
  showPlaceholder,
  allowFocus,
  id: cellId,
  code,
  status,
  serializedEditorState,
  mode,
  runCell,
  updateCellCode,
  createNewCell,
  deleteCell,
  focusCell,
  moveCell,
  moveToNextCell,
  updateCellConfig,
  userConfig,
  editorViewRef,
  hidden,
}: CellEditorProps) => {
  const [canUseMarkdown, setCanUseMarkdown] = useState(false);

  // DOM node where the editorView will be mounted
  const editorViewParentRef = useRef<HTMLDivElement>(null);

  const loading = status === "running" || status === "queued";
  const editing = mode === "edit";
  const reading = mode === "read";
  const { sendToTop, sendToBottom } = useCellActions();

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
    [cellId, createNewCell],
  );
  const createAbove = useCallback(
    () => createNewCell({ cellId, before: true }),
    [cellId, createNewCell],
  );
  const moveDown = useCallback(
    () => moveCell({ cellId, before: false }),
    [cellId, moveCell],
  );
  const moveUp = useCallback(
    () => moveCell({ cellId, before: true }),
    [cellId, moveCell],
  );
  const focusDown = useCallback(
    () => focusCell({ cellId, before: false }),
    [cellId, focusCell],
  );
  const focusUp = useCallback(
    () => focusCell({ cellId, before: true }),
    [cellId, focusCell],
  );
  const toggleHideCode = useEvent(() => {
    const newConfig: CellConfig = { hide_code: !hidden };
    // Fire-and-forget save
    void saveCellConfig({ configs: { [cellId]: newConfig } });
    updateCellConfig({ cellId, config: newConfig });
    return newConfig.hide_code || false;
  });

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
        onRun: runCell,
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
        toggleHideCode,
      },
      completionConfig: userConfig.completion,
      keymapConfig: userConfig.keymap,
      theme,
    });

    // listen to code changes if we can use markdown
    extensions.push(
      ViewPlugin.define(() => ({
        update(view) {
          const code = view.state.doc.toString();
          const languageAdapter = view.state.field(languageAdapterState);
          // If its not markdown, set if we can use markdown
          if (languageAdapter.type !== "markdown") {
            setCanUseMarkdown(LanguageAdapters.markdown().isSupported(code));
          }
        },
      })),
    );

    // Should focus will be true if its a newly created editor
    let shouldFocus: boolean;
    if (serializedEditorState === null) {
      // If the editor already exists, reconfigure it with the new extensions.
      // Triggered when, e.g., placeholder changes.
      if (editorViewRef.current === null) {
        // Otherwise, create a new editor.
        editorViewRef.current = new EditorView({
          state: EditorState.create({
            doc: code,
            extensions: extensions,
          }),
        });
        shouldFocus = true;
      } else {
        editorViewRef.current.dispatch({
          effects: [
            StateEffect.reconfigure.of([extensions]),
            reconfigureLanguageEffect(
              editorViewRef.current,
              userConfig.completion,
            ),
          ],
        });
        shouldFocus = false;
      }
    } else {
      editorViewRef.current = new EditorView({
        state: EditorState.fromJSON(
          serializedEditorState,
          {
            doc: code,
            extensions: extensions,
          },
          { history: historyField },
        ),
      });
      shouldFocus = true;
    }

    if (
      editorViewRef.current !== null &&
      editorViewParentRef.current !== null
    ) {
      // Always replace the children in case the editor view was re-created.
      editorViewParentRef.current.replaceChildren(editorViewRef.current.dom);
    }

    if (shouldFocus && allowFocus) {
      // Focus and scroll into view; request an animation frame to
      // avoid a race condition when new editors are created
      // very rapidly by holding a hotkey
      requestAnimationFrame(() => {
        editorViewRef.current?.focus();
        editorViewRef.current?.dom.scrollIntoView({
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
    runCell,
    serializedEditorState,
  ]);

  useLayoutEffect(() => {
    if (editorViewRef.current === null) {
      return;
    }
    if (
      editing &&
      editorViewParentRef.current !== null &&
      editorViewRef.current !== null
    ) {
      editorViewParentRef.current.replaceChildren(editorViewRef.current.dom);
    }
  }, [editing, editorViewRef]);

  const showCode = async () => {
    if (hidden) {
      await saveCellConfig({ configs: { [cellId]: { hide_code: false } } });
      updateCellConfig({ cellId, config: { hide_code: false } });
      // Focus on the editor view
      editorViewRef.current?.focus();
    }
  };

  return (
    <>
      {canUseMarkdown && (
        <div className="absolute top-1 right-1">
          <LanguageToggle
            editorView={derefNotNull(editorViewRef)}
            canUseMarkdown={canUseMarkdown}
          />
        </div>
      )}
      {hidden && <HideCodeButton onClick={showCode} />}
      <div
        className={cn("cm", hidden && "opacity-20 h-8 overflow-hidden")}
        ref={editorViewParentRef}
      />
    </>
  );
};

export const CellEditor = memo(CellEditorInternal);
