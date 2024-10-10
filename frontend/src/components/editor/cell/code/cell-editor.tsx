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
import { type CellActions, useCellActions } from "@/core/cells/cells";
import type { CellRuntimeState, CellData } from "@/core/cells/types";
import type { UserConfig } from "@/core/config/config-schema";
import type { Theme } from "@/theme/useTheme";
import {
  getInitialLanguageAdapter,
  languageAdapterState,
  reconfigureLanguageEffect,
  switchLanguage,
} from "@/core/codemirror/language/extension";
import { LanguageToggles } from "./language-toggle";
import { cn } from "@/utils/cn";
import { saveCellConfig } from "@/core/network/requests";
import { HideCodeButton } from "../../code/readonly-python-code";
import { AiCompletionEditor } from "./ai-completion-editor";
import { useAtom, useAtomValue } from "jotai";
import { aiCompletionCellAtom } from "@/core/ai/state";
import { mergeRefs } from "@/utils/mergeRefs";
import { useSetLastFocusedCellId } from "@/core/cells/focus";
import type { LanguageAdapterType } from "@/core/codemirror/language/types";
import { autoInstantiateAtom, isAiEnabled } from "@/core/config/config";
import { maybeAddMarimoImport } from "@/core/cells/add-missing-import";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import { useSplitCellCallback } from "../useSplitCell";
import { MarkdownLanguageAdapter } from "@/core/codemirror/language/markdown";

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
      | "updateCellConfig"
      | "clearSerializedEditorState"
    > {
  runCell: () => void;
  moveToNextCell: CellActions["moveToNextCell"] | undefined;
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
  const [aiCompletionCell, setAiCompletionCell] = useAtom(aiCompletionCellAtom);
  const [languageAdapter, setLanguageAdapter] = useState<LanguageAdapterType>();
  const setLastFocusedCellId = useSetLastFocusedCellId();
  // DOM node where the editorView will be mounted
  const editorViewParentRef = useRef<HTMLDivElement>(null);

  const loading = status === "running" || status === "queued";
  const { sendToTop, sendToBottom } = useCellActions();
  const splitCell = useSplitCellCallback();

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
    const nextHidden = !hidden;
    // Fire-and-forget save
    void saveCellConfig({ configs: { [cellId]: { hide_code: nextHidden } } });
    updateCellConfig({ cellId, config: { hide_code: nextHidden } });
    return nextHidden;
  });
  const autoInstantiate = useAtomValue(autoInstantiateAtom);
  const afterToggleMarkdown = useEvent(() => {
    maybeAddMarimoImport(autoInstantiate, createNewCell);
  });

  const aiEnabled = isAiEnabled(userConfig);

  const extensions = useMemo(() => {
    const extensions = setupCodeMirror({
      cellId,
      showPlaceholder,
      enableAI: aiEnabled,
      cellCodeCallbacks: {
        updateCellCode,
        afterToggleMarkdown,
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
        splitCell,
        moveToNextCell,
        toggleHideCode,
        aiCellCompletion: () => {
          let closed = false;
          setAiCompletionCell((v) => {
            // Toggle close
            if (v?.cellId === cellId) {
              closed = true;
              return null;
            }
            return { cellId };
          });
          return closed;
        },
      },
      completionConfig: userConfig.completion,
      keymapConfig: userConfig.keymap,
      theme,
      hotkeys: new OverridingHotkeyProvider(userConfig.keymap.overrides ?? {}),
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
            const languageAdapter = view.state.field(languageAdapterState);
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
    aiEnabled,
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
    splitCell,
    toggleHideCode,
    updateCellCode,
    handleDelete,
    runCell,
    setAiCompletionCell,
    afterToggleMarkdown,
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
              new OverridingHotkeyProvider(userConfig.keymap.overrides ?? {}),
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
          block: "nearest",
        });
      });
    }

    // We don't want to re-run this effect when `allowFocus` or `code` changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    editorViewRef,
    extensions,
    userConfig.completion,
    userConfig.keymap,
    clearSerializedEditorState,
    cellId,
    serializedEditorState,
  ]);

  // Destroy the editor when the component is unmounted
  useEffect(() => {
    return () => {
      editorViewRef.current?.destroy();
    };
  }, [editorViewRef]);

  const temporarilyShowCode = useCallback(async () => {
    if (hidden) {
      updateCellConfig({ cellId, config: { hide_code: false } });
      editorViewRef.current?.focus();
      editorViewParentRef.current?.addEventListener(
        "focusout",
        () => updateCellConfig({ cellId, config: { hide_code: true } }),
        { once: true },
      );
    }
  }, [hidden, cellId, updateCellConfig, editorViewRef]);

  // For a newly created Markdown cell, which defaults to
  // hidden code, we temporarily show the code editor
  useEffect(() => {
    if (code === new MarkdownLanguageAdapter().defaultCode) {
      return;
    }
    temporarilyShowCode();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);

  return (
    <AiCompletionEditor
      enabled={aiCompletionCell?.cellId === cellId}
      initialPrompt={aiCompletionCell?.initialPrompt}
      currentCode={editorViewRef.current?.state.doc.toString() ?? code}
      currentLanguageAdapter={languageAdapter}
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
        {hidden && <HideCodeButton onClick={temporarilyShowCode} />}
        <CellCodeMirrorEditor
          className={cn(hidden && "opacity-20 h-8 overflow-hidden")}
          editorView={editorViewRef.current}
          ref={editorViewParentRef}
        />
        {!hidden && (
          <div className="absolute top-1 right-5">
            <LanguageToggles
              code={code}
              editorView={editorViewRef.current}
              currentLanguageAdapter={languageAdapter}
              onAfterToggle={afterToggleMarkdown}
            />
          </div>
        )}
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
