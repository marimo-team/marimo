/* Copyright 2024 Marimo. All rights reserved. */
import { historyField } from "@codemirror/commands";
import { EditorState, StateEffect } from "@codemirror/state";
import { EditorView, ViewPlugin } from "@codemirror/view";
import React, { memo, useCallback, useEffect, useRef, useMemo } from "react";

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
import { AiCompletionEditor } from "../../ai/ai-completion-editor";
import { useAtom, useAtomValue } from "jotai";
import { aiCompletionCellAtom } from "@/core/ai/state";
import { mergeRefs } from "@/utils/mergeRefs";
import { useSetLastFocusedCellId } from "@/core/cells/focus";
import type { LanguageAdapterType } from "@/core/codemirror/language/types";
import { autoInstantiateAtom, isAiEnabled } from "@/core/config/config";
import { maybeAddMarimoImport } from "@/core/cells/add-missing-import";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import { useSplitCellCallback } from "../useSplitCell";
import { invariant } from "@/utils/invariant";

export interface CellEditorProps
  extends Pick<CellRuntimeState, "status">,
    Pick<CellData, "id" | "code" | "serializedEditorState" | "config">,
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
  setEditorView: (view: EditorView) => void;
  /**
   * If true, the cell is allowed to be focus on.
   * This is false when the app is initially loading.
   */
  allowFocus: boolean;
  userConfig: UserConfig;
  /**
   * If true, the cell code is hidden.
   * This is different from cellConfig.hide_code, since it may be temporarily shown.
   */
  hidden?: boolean;
  languageAdapter: LanguageAdapterType | undefined;
  setLanguageAdapter: React.Dispatch<
    React.SetStateAction<LanguageAdapterType | undefined>
  >;
  // Props below are not used by scratchpad.
  // DOM node where the editorView will be mounted
  editorViewParentRef?: React.MutableRefObject<HTMLDivElement | null>;
  temporarilyShowCode: () => void;
}

const CellEditorInternal = ({
  theme,
  showPlaceholder,
  allowFocus,
  id: cellId,
  config: cellConfig,
  code,
  status,
  serializedEditorState,
  setEditorView,
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
  editorViewParentRef,
  hidden,
  temporarilyShowCode,
  languageAdapter,
  setLanguageAdapter,
}: CellEditorProps) => {
  const [aiCompletionCell, setAiCompletionCell] = useAtom(aiCompletionCellAtom);
  const setLastFocusedCellId = useSetLastFocusedCellId();

  const loading = status === "running" || status === "queued";
  const { sendToTop, sendToBottom } = useCellActions();
  const splitCell = useSplitCellCallback();

  const isMarkdown = languageAdapter === "markdown";

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
    // Use cellConfig.hide_code instead of hidden, since it may be temporarily shown
    const nextHidden = !cellConfig.hide_code;
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
        createManyBelow: (cells) => {
          for (const code of [...cells].reverse()) {
            createNewCell({
              code,
              before: false,
              cellId: cellId,
              // If the code already exists, skip creation
              skipIfCodeExists: true,
            });
          }
        },
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
    setLanguageAdapter,
  ]);

  const handleInitializeEditor = useEvent(() => {
    // Create a new editor
    const ev = new EditorView({
      state: EditorState.create({
        doc: code,
        extensions: extensions,
      }),
    });
    setEditorView(ev);
    // Initialize the language adapter
    switchLanguage(ev, getInitialLanguageAdapter(ev.state).type);
  });

  const handleReconfigureEditor = useEvent(() => {
    invariant(editorViewRef.current !== null, "Editor view is not initialized");
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
  });

  const handleDeserializeEditor = useEvent(() => {
    invariant(serializedEditorState, "Editor view is not initialized");
    const ev = new EditorView({
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
    switchLanguage(ev, getInitialLanguageAdapter(ev.state).type);
    setEditorView(ev);
    // Clear the serialized state so that we don't re-create the editor next time
    clearSerializedEditorState({ cellId });
  });

  useEffect(() => {
    if (serializedEditorState === null) {
      if (editorViewRef.current === null) {
        handleInitializeEditor();
      } else {
        // If the editor already exists, reconfigure it with the new extensions.
        handleReconfigureEditor();
      }
    } else {
      handleDeserializeEditor();
    }

    if (
      editorViewRef.current !== null &&
      editorViewParentRef &&
      editorViewParentRef.current !== null
    ) {
      // Always replace the children in case the editor view was re-created.
      editorViewParentRef.current.replaceChildren(editorViewRef.current.dom);
    }
  }, [
    handleInitializeEditor,
    handleReconfigureEditor,
    handleDeserializeEditor,
    editorViewRef,
    editorViewParentRef,
    serializedEditorState,
    // Props to trigger reconfiguration
    extensions,
  ]);

  // Auto-focus. Should focus newly created editors.
  const shouldFocus =
    editorViewRef.current === null || serializedEditorState !== null;
  useEffect(() => {
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
  }, [shouldFocus, allowFocus, editorViewRef]);

  // Destroy the editor when the component is unmounted
  useEffect(() => {
    const ev = editorViewRef.current;
    return () => {
      ev?.destroy();
    };
  }, [editorViewRef]);

  return (
    <AiCompletionEditor
      enabled={aiCompletionCell?.cellId === cellId}
      initialPrompt={aiCompletionCell?.initialPrompt}
      currentCode={editorViewRef.current?.state.doc.toString() ?? code}
      currentLanguageAdapter={languageAdapter}
      declineChange={useEvent(() => {
        setAiCompletionCell(null);
        editorViewRef.current?.focus();
      })}
      onChange={useEvent((newCode) => {
        editorViewRef.current?.dispatch({
          changes: {
            from: 0,
            to: editorViewRef.current.state.doc.length,
            insert: newCode,
          },
        });
      })}
      acceptChange={useEvent((newCode) => {
        editorViewRef.current?.dispatch({
          changes: {
            from: 0,
            to: editorViewRef.current.state.doc.length,
            insert: newCode,
          },
        });
        editorViewRef.current?.focus();
        setAiCompletionCell(null);
      })}
    >
      <div
        className="relative w-full"
        onFocus={() => setLastFocusedCellId(cellId)}
      >
        {/* Completely hide the editor and icons when markdown is hidden. If just hidden, display. */}
        {!isMarkdown && hidden && (
          <HideCodeButton
            tooltip="Edit code"
            className="absolute inset-0 z-10"
            onClick={temporarilyShowCode}
          />
        )}
        <CellCodeMirrorEditor
          className={cn(
            isMarkdown && hidden
              ? "h-0 overflow-hidden"
              : hidden && "opacity-20 h-8 overflow-hidden",
          )}
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
    ref?: React.Ref<HTMLDivElement>,
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
        ref={(r) => {
          if (ref) {
            mergeRefs(ref, internalRef)(r);
          } else {
            mergeRefs(internalRef)(r);
          }
        }}
        data-testid="cell-editor"
      />
    );
  },
);
CellCodeMirrorEditor.displayName = "CellCodeMirrorEditor";

export const CellEditor = memo(CellEditorInternal);
