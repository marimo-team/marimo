/* Copyright 2024 Marimo. All rights reserved. */
import { historyField } from "@codemirror/commands";
import { EditorState, StateEffect } from "@codemirror/state";
import { EditorView, ViewPlugin } from "@codemirror/view";
import { useAtom, useAtomValue } from "jotai";
import React, { memo, useEffect, useMemo, useRef } from "react";
import useEvent from "react-use-event-hook";
import { Button } from "@/components/ui/button";
import { DelayMount } from "@/components/utils/delay-mount";
import { aiCompletionCellAtom } from "@/core/ai/state";
import { maybeAddMarimoImport } from "@/core/cells/add-missing-import";
import { useCellActions } from "@/core/cells/cells";
import { usePendingDeleteService } from "@/core/cells/pending-delete-service";
import type { CellData, CellRuntimeState } from "@/core/cells/types";
import { setupCodeMirror } from "@/core/codemirror/cm";
import {
  getInitialLanguageAdapter,
  languageAdapterState,
  reconfigureLanguageEffect,
  switchLanguage,
} from "@/core/codemirror/language/extension";
import type { LanguageAdapterType } from "@/core/codemirror/language/types";
import {
  connectedDocAtom,
  realTimeCollaboration,
} from "@/core/codemirror/rtc/extension";
import { autoInstantiateAtom, isAiEnabled } from "@/core/config/config";
import type { UserConfig } from "@/core/config/config-schema";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import { connectionAtom } from "@/core/network/connection";
import { saveCellConfig } from "@/core/network/requests";
import { isRtcEnabled } from "@/core/rtc/state";
import { useSaveNotebook } from "@/core/saving/save-component";
import { WebSocketState } from "@/core/websocket/types";
import type { Theme } from "@/theme/useTheme";
import { cn } from "@/utils/cn";
import { invariant } from "@/utils/invariant";
import { mergeRefs } from "@/utils/mergeRefs";
import { AiCompletionEditor } from "../../ai/ai-completion-editor";
import { HideCodeButton } from "../../code/readonly-python-code";
import { useCellEditorNavigationProps } from "../../navigation/navigation";
import { useDeleteCellCallback } from "../useDeleteCell";
import { useSplitCellCallback } from "../useSplitCell";
import { LanguageToggles } from "./language-toggle";

export interface CellEditorProps
  extends Pick<CellRuntimeState, "status">,
    Pick<CellData, "id" | "code" | "serializedEditorState" | "config"> {
  runCell: () => void;
  theme: Theme;
  showPlaceholder: boolean;
  editorViewRef: React.MutableRefObject<EditorView | null>;
  setEditorView: (view: EditorView) => void;
  userConfig: UserConfig;
  /**
   * If true, the cell code is hidden.
   * This is different from cellConfig.hide_code, since it may be temporarily shown.
   */
  hidden?: boolean;
  hasOutput?: boolean;
  languageAdapter: LanguageAdapterType | undefined;
  showLanguageToggles?: boolean;
  setLanguageAdapter: React.Dispatch<
    React.SetStateAction<LanguageAdapterType | undefined>
  >;
  // Props below are not used by scratchpad.
  // DOM node where the editorView will be mounted
  editorViewParentRef?: React.MutableRefObject<HTMLDivElement | null>;
  showHiddenCode: (opts?: { focus?: boolean }) => void;
}

const CellEditorInternal = ({
  theme,
  showPlaceholder,
  id: cellId,
  config: cellConfig,
  code,
  status,
  serializedEditorState,
  setEditorView,
  runCell,
  userConfig,
  editorViewRef,
  editorViewParentRef,
  hidden,
  hasOutput,
  showHiddenCode,
  languageAdapter,
  setLanguageAdapter,
  showLanguageToggles = true,
}: CellEditorProps) => {
  const [aiCompletionCell, setAiCompletionCell] = useAtom(aiCompletionCellAtom);
  const deleteCell = useDeleteCellCallback();
  const { saveOrNameNotebook } = useSaveNotebook();
  const pendingDeleteService = usePendingDeleteService();

  const loading = status === "running" || status === "queued";
  const cellActions = useCellActions();
  const splitCell = useSplitCellCallback();

  const isMarkdown = languageAdapter === "markdown";

  const handleDelete = useEvent(() => {
    // Cannot delete running cells, since we're waiting for their output.
    if (loading) {
      return false;
    }

    if (pendingDeleteService.idle && userConfig.keymap.destructive_delete) {
      pendingDeleteService.submit([cellId]);
      return true;
    }

    deleteCell({ cellId });
    return true;
  });

  const handleRunCell = useEvent(() => {
    if (loading) {
      return false;
    }
    runCell();
    return true;
  });

  const toggleHideCode = useEvent(() => {
    // Use cellConfig.hide_code instead of hidden, since it may be temporarily shown
    const nextHidden = !cellConfig.hide_code;
    // Fire-and-forget save
    void saveCellConfig({ configs: { [cellId]: { hide_code: nextHidden } } });
    cellActions.updateCellConfig({ cellId, config: { hide_code: nextHidden } });
    return nextHidden;
  });

  const autoInstantiate = useAtomValue(autoInstantiateAtom);
  const afterToggleMarkdown = useEvent(() => {
    maybeAddMarimoImport({
      autoInstantiate,
      createNewCell: cellActions.createNewCell,
    });
  });

  const aiEnabled = isAiEnabled(userConfig);

  const extensions = useMemo(() => {
    const extensions = setupCodeMirror({
      cellId,
      showPlaceholder,
      enableAI: aiEnabled,
      cellActions: {
        ...cellActions,
        afterToggleMarkdown,
        onRun: handleRunCell,
        deleteCell: handleDelete,
        saveNotebook: saveOrNameNotebook,
        createManyBelow: (cells) => {
          for (const code of [...cells].reverse()) {
            cellActions.createNewCell({
              code,
              before: false,
              cellId: cellId,
              // If the code already exists, skip creation
              skipIfCodeExists: true,
            });
          }
        },
        splitCell,
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
      lspConfig: userConfig.language_servers,
      theme,
      hotkeys: new OverridingHotkeyProvider(userConfig.keymap.overrides ?? {}),
      diagnosticsConfig: userConfig.diagnostics,
      displayConfig: userConfig.display,
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
      // Listen to selection changes, and show the code if it is hidden
      EditorView.updateListener.of((update) => {
        if (update.selectionSet) {
          const selection = update.state.selection;
          const hasSelection = selection.ranges.some(
            (range) => range.from !== range.to,
          );

          if (hasSelection) {
            showHiddenCode({ focus: false });
          }
        }
      }),
    );

    return extensions;
  }, [
    cellId,
    userConfig.keymap,
    userConfig.completion,
    userConfig.language_servers,
    userConfig.display,
    userConfig.diagnostics,
    aiEnabled,
    theme,
    showPlaceholder,
    cellActions,
    splitCell,
    toggleHideCode,
    handleDelete,
    handleRunCell,
    setAiCompletionCell,
    afterToggleMarkdown,
    setLanguageAdapter,
    showHiddenCode,
    saveOrNameNotebook,
  ]);

  const rtcEnabled = isRtcEnabled();
  const handleInitializeEditor = useEvent(() => {
    // If rtc is enabled, use collaborative editing
    if (rtcEnabled) {
      const rtc = realTimeCollaboration(
        cellId,
        (code) => {
          // It's not really a formatting change,
          // but this means it won't be marked as stale
          cellActions.updateCellCode({ cellId, code, formattingChange: true });
        },
        code,
      );
      extensions.push(rtc.extension);
      code = rtc.code;
    }

    // Create a new editor
    const ev = new EditorView({
      state: EditorState.create({
        doc: code,
        extensions: extensions,
      }),
    });
    setEditorView(ev);
    // Initialize the language adapter
    if (!rtcEnabled) {
      switchLanguage(ev, {
        language: getInitialLanguageAdapter(ev.state).type,
      });
    }
  });

  const handleReconfigureEditor = useEvent(() => {
    invariant(editorViewRef.current !== null, "Editor view is not initialized");
    // If rtc is enabled, use collaborative editing
    if (rtcEnabled) {
      const rtc = realTimeCollaboration(cellId, (code) => {
        // It's not really a formatting change,
        // but this means it won't be marked as stale
        cellActions.updateCellCode({ cellId, code, formattingChange: true });
      });
      extensions.push(rtc.extension);
    }

    editorViewRef.current.dispatch({
      effects: [
        StateEffect.reconfigure.of([extensions]),
        reconfigureLanguageEffect(editorViewRef.current, {
          completionConfig: userConfig.completion,
          hotkeysProvider: new OverridingHotkeyProvider(
            userConfig.keymap.overrides ?? {},
          ),
          lspConfig: {
            ...userConfig.language_servers,
            diagnostics: userConfig.diagnostics,
          },
        }),
      ],
    });
  });

  const handleDeserializeEditor = useEvent(() => {
    invariant(serializedEditorState, "Editor view is not initialized");
    if (rtcEnabled) {
      const rtc = realTimeCollaboration(
        cellId,
        (code) => {
          // It's not really a formatting change,
          // but this means it won't be marked as stale
          cellActions.updateCellCode({ cellId, code, formattingChange: true });
        },
        code,
      );
      extensions.push(rtc.extension);
      code = rtc.code;
    }

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
    if (!rtcEnabled) {
      switchLanguage(ev, {
        language: getInitialLanguageAdapter(ev.state).type,
      });
    }
    setEditorView(ev);
    // Clear the serialized state so that we don't re-create the editor next time
    cellActions.clearSerializedEditorState({ cellId });
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

  // Destroy the editor when the component is unmounted
  useEffect(() => {
    const ev = editorViewRef.current;
    return () => {
      ev?.destroy();
    };
  }, [editorViewRef]);

  const navigationProps = useCellEditorNavigationProps(cellId);

  // Completely hide the editor & icons if it's markdown and hidden. If there is output, we show.
  const showHideButton =
    (hidden && !isMarkdown) || (hidden && isMarkdown && !hasOutput);

  let editorClassName = "";
  if (isMarkdown && hidden && hasOutput) {
    editorClassName = "h-0 overflow-hidden";
  } else if (hidden) {
    editorClassName =
      "opacity-20 h-8 [&>div.cm-editor]:h-full [&>div.cm-editor]:overflow-hidden";
  }

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
      <div className="relative w-full" {...navigationProps}>
        {showHideButton && (
          <HideCodeButton
            tooltip="Edit code"
            className="absolute inset-0 z-10"
            onClick={showHiddenCode}
          />
        )}
        <CellCodeMirrorEditor
          className={editorClassName}
          editorView={editorViewRef.current}
          ref={editorViewParentRef}
        />
        {!hidden && showLanguageToggles && (
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
        className={cn("cm mathjax_ignore", className)}
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

// Wait until the websocket connection is open before rendering the editor
// This is used for real-time collaboration since the backend needs the connection started
// before connecting the rtc websockets
function WithWaitUntilConnected<T extends {}>(
  Component: React.ComponentType<T>,
) {
  // biome-ignore lint/nursery/noNestedComponentDefinitions: this is evaluated top-level
  const WaitUntilConnectedComponent = (props: T) => {
    const connection = useAtomValue(connectionAtom);
    const [rtcDoc, setRtcDoc] = useAtom(connectedDocAtom);

    if (
      connection.state === WebSocketState.CONNECTING ||
      rtcDoc === undefined
    ) {
      return (
        <div className="flex h-full w-full items-baseline p-4">
          <DelayMount milliseconds={1000} fallback={null}>
            <span>Waiting for real-time collaboration connection...</span>
            <Button
              variant="link"
              onClick={() => {
                setRtcDoc("disabled");
              }}
            >
              Turn off real-time collaboration
            </Button>
          </DelayMount>
        </div>
      );
    }

    return <Component {...props} />;
  };

  WaitUntilConnectedComponent.displayName = `WithWaitUntilConnected(${Component.displayName})`;
  return WaitUntilConnectedComponent;
}

export const CellEditor = isRtcEnabled()
  ? WithWaitUntilConnected(memo(CellEditorInternal))
  : memo(CellEditorInternal);
