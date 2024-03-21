/* Copyright 2024 Marimo. All rights reserved. */
import { historyField } from "@codemirror/commands";
import { EditorState, StateEffect } from "@codemirror/state";
import { EditorView, ViewPlugin } from "@codemirror/view";
import React, {
  memo,
  useCallback,
  useEffect,
  useRef,
  useState,
  useMemo,
} from "react";

import { setupCodeMirror } from "@/core/codemirror/cm";
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
import { AiCompletionEditor } from "./ai-completion-editor";
import { useAtom, useSetAtom } from "jotai";
import { aiCompletionCellAtom } from "@/core/ai/state";
import { mergeRefs } from "@/utils/mergeRefs";
import { lastFocusedCellIdAtom } from "@/core/cells/focus";

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
      | "clearSerializedEditorState"
    > {
  runCell: () => void;
  theme: Theme;
  showPlaceholder: boolean;
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
  runCell,
  updateCellCode,
  createNewCell,
  deleteCell,
  focusCell,
  moveCell,
  moveToNextCell,
  updateCellConfig,
  clearSerializedEditorState,
  userConfig,
  editorViewRef,
  hidden,
}: CellEditorProps) => {
  const [canUseMarkdown, setCanUseMarkdown] = useState(false);
  const [aiCompletionCell, setAiCompletionCell] = useAtom(aiCompletionCellAtom);
  const setLastFocusedCellId = useSetAtom(lastFocusedCellIdAtom);
  // DOM node where the editorView will be mounted
  const editorViewParentRef = useRef<HTMLDivElement>(null);

  const loading = status === "running" || status === "queued";
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

  const extensions = useMemo(() => {
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
        aiCellCompletion: () => {
          let closed = false;
          setAiCompletionCell((v) => {
            if (v === cellId) {
              closed = true;
              return null;
            }
            return cellId;
          });
          return closed;
        },
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

    return extensions;
  }, [
    cellId,
    userConfig.keymap,
    userConfig.completion,
    theme,
    showPlaceholder,
    createAbove,
    createBelow,
    focusUp,
    focusDown,
    moveUp,
    moveDown,
    moveToNextCell,
    sendToTop,
    sendToBottom,
    toggleHideCode,
    updateCellCode,
    handleDelete,
    runCell,
    setAiCompletionCell,
  ]);

  useEffect(() => {
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
      // Clear the serialized state so that we don't re-create the editor next time
      clearSerializedEditorState({ cellId });
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
    editorViewRef,
    extensions,
    userConfig.completion,
    clearSerializedEditorState,
    cellId,
    serializedEditorState,
  ]);

  const showCode = async () => {
    if (hidden) {
      await saveCellConfig({ configs: { [cellId]: { hide_code: false } } });
      updateCellConfig({ cellId, config: { hide_code: false } });
      // Focus on the editor view
      editorViewRef.current?.focus();
    }
  };

  return (
    <AiCompletionEditor
      enabled={aiCompletionCell === cellId}
      currentCode={code}
      declineChange={() => {
        setAiCompletionCell(null);
        editorViewRef.current?.focus();
      }}
      onChange={(newCode) => {
        editorViewRef.current?.dispatch({
          changes: {
            from: 0,
            to: editorViewRef.current.state.doc.length,
            insert: newCode,
          },
        });
      }}
      acceptChange={(newCode) => {
        editorViewRef.current?.dispatch({
          changes: {
            from: 0,
            to: editorViewRef.current.state.doc.length,
            insert: newCode,
          },
        });
        editorViewRef.current?.focus();
        setAiCompletionCell(null);
      }}
    >
      <div
        className="relative w-full"
        onFocus={() => setLastFocusedCellId(cellId)}
      >
        {canUseMarkdown && (
          <div className="absolute top-1 right-1">
            <LanguageToggle
              editorView={derefNotNull(editorViewRef)}
              canUseMarkdown={canUseMarkdown}
            />
          </div>
        )}
        {hidden && <HideCodeButton onClick={showCode} />}
        <CellCodeMirrorEditor
          className={cn(hidden && "opacity-20 h-8 overflow-hidden")}
          editorView={editorViewRef.current}
          ref={editorViewParentRef}
        />
      </div>
    </AiCompletionEditor>
  );
};

const CellCodeMirrorEditor = React.forwardRef(
  (
    props: {
      className?: string;
      editorView: EditorView | null;
    },
    ref: React.Ref<HTMLDivElement>,
  ) => {
    const { className, editorView } = props;
    const internalRef = useRef<HTMLDivElement>(null);

    // If this gets unmounted/remounted, we need to re-append the editorView
    useEffect(() => {
      if (editorView === null) {
        return;
      }
      if (internalRef.current === null) {
        return;
      }
      // Has no children, so we can replaceChildren
      if (internalRef.current.children.length === 0) {
        internalRef.current.append(editorView.dom);
      }
    }, [editorView, internalRef]);

    return (
      <div className={cn("cm", className)} ref={mergeRefs(ref, internalRef)} />
    );
  },
);
CellCodeMirrorEditor.displayName = "CellCodeMirrorEditor";

export const CellEditor = memo(CellEditorInternal);
