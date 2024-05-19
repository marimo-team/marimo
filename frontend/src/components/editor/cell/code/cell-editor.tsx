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
  getInitialLanguageAdapter,
  languageAdapterState,
  reconfigureLanguageEffect,
  switchLanguage,
} from "@/core/codemirror/language/extension";
import { LanguageToggle } from "./language-toggle";
import { cn } from "@/utils/cn";
import { saveCellConfig } from "@/core/network/requests";
import { HideCodeButton } from "../../code/readonly-python-code";
import { AiCompletionEditor } from "./ai-completion-editor";
import { useAtom, useSetAtom } from "jotai";
import { aiCompletionCellAtom } from "@/core/ai/state";
import { mergeRefs } from "@/utils/mergeRefs";
import { lastFocusedCellIdAtom } from "@/core/cells/focus";
import { LanguageAdapter } from "@/core/codemirror/language/types";
import { getPositionAtWordBounds } from "@/core/codemirror/completion/hints";
import { useVariables } from "@/core/variables/state";
import { VariableName, Variables } from "@/core/variables/types";
import { goToDefinition } from "@/core/codemirror/find-replace/search-highlight";

export interface CellEditorProps
  extends Pick<CellRuntimeState, "status">,
    Pick<CellData, "id" | "code" | "serializedEditorState">,
    Pick<
      CellActions,
      | "updateCellCode"
      | "createNewCell"
      | "deleteCell"
      | "focusCell"
      | "focusCellAtDefinition"
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
  focusCellAtDefinition,
  moveCell,
  moveToNextCell,
  updateCellConfig,
  clearSerializedEditorState,
  userConfig,
  editorViewRef,
  hidden,
}: CellEditorProps) => {
  const [canUseMarkdown, setCanUseMarkdown] = useState(() => {
    return LanguageAdapters.markdown().isSupported(code);
  });
  const [aiCompletionCell, setAiCompletionCell] = useAtom(aiCompletionCellAtom);
  const [languageAdapter, setLanguageAdapter] =
    useState<LanguageAdapter["type"]>();
  const setLastFocusedCellId = useSetAtom(lastFocusedCellIdAtom);
  // DOM node where the editorView will be mounted
  const editorViewParentRef = useRef<HTMLDivElement>(null);
  const variables = useVariables();

  const loading = status === "running" || status === "queued";
  const { splitCell, sendToTop, sendToBottom } = useCellActions();

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
  const focusByVariableName = useCallback(() => {
    if (editorViewRef.current) {
      const { state } = editorViewRef.current;
      const variableName = getWordUnderCursor(state);
      const focusCellId = getCellIdOfDefinition(variables, variableName);

      if (focusCellId) {
        focusCellAtDefinition({
          cellId: focusCellId,
          variableName: variableName,
        });
      }
      return true;
    }
  }, [editorViewRef, focusCellAtDefinition, variables]);
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
      enableAI: Boolean(userConfig.ai.open_ai?.api_key),
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
        focusByVariableName,
        focusUp,
        focusDown,
        sendToTop,
        sendToBottom,
        splitCell,
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

    extensions.push(
      // Listen to code changes if we can use markdown
      // Also update the language adapter
      ViewPlugin.define((view) => {
        // Init
        const languageAdapter = view.state.field(languageAdapterState);
        setLanguageAdapter(languageAdapter.type);

        return {
          update(view) {
            const code = view.state.doc.toString();
            const languageAdapter = view.state.field(languageAdapterState);
            // If its not markdown, set if we can use markdown
            if (languageAdapter.type !== "markdown") {
              setCanUseMarkdown(LanguageAdapters.markdown().isSupported(code));
            }

            // Set the language adapter
            setLanguageAdapter(languageAdapter.type);
          },
        };
      }),
    );

    return extensions;
  }, [
    cellId,
    userConfig.keymap,
    userConfig.completion,
    userConfig.ai.open_ai?.api_key,
    theme,
    showPlaceholder,
    createAbove,
    createBelow,
    focusByVariableName,
    focusUp,
    focusDown,
    moveUp,
    moveDown,
    moveToNextCell,
    sendToTop,
    sendToBottom,
    splitCell,
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
        // Initialize the language adapter
        switchLanguage(
          editorViewRef.current,
          getInitialLanguageAdapter(editorViewRef.current.state).type,
        );
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
      // Initialize the language adapter
      switchLanguage(
        editorViewRef.current,
        getInitialLanguageAdapter(editorViewRef.current.state).type,
      );
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
        {canUseMarkdown && !hidden && (
          <div className="absolute top-1 right-1">
            <LanguageToggle
              editorView={editorViewRef.current}
              languageAdapter={languageAdapter}
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
      <div
        className={cn("cm", className)}
        ref={mergeRefs(ref, internalRef)}
        data-testid="cell-editor"
      />
    );
  },
);
CellCodeMirrorEditor.displayName = "CellCodeMirrorEditor";

export const CellEditor = memo(CellEditorInternal);

export const getWordUnderCursor = (state: EditorState) => {
  const { from, to } = state.selection.main;
  let variableName: string;

  if (from === to) {
    const { startToken, endToken } = getPositionAtWordBounds(state.doc, from);
    variableName = state.doc.sliceString(startToken, endToken);
  } else {
    variableName = state.doc.sliceString(from, to);
  }

  return variableName;
};

export const getCellIdOfDefinition = (
  variables: Variables,
  variableName: string,
) => {
  const variable = variables[variableName as VariableName];
  if (!variable || variable.declaredBy.length === 0) {
    return null;
  }
  const focusCellId = variable.declaredBy[0];
  return focusCellId;
};
