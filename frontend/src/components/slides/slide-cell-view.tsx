/* Copyright 2026 Marimo. All rights reserved. */

import { useMemo, useRef, useState } from "react";
import type { EditorView } from "@codemirror/view";
import { useAtomValue } from "jotai";
import useEvent from "react-use-event-hook";
import { cellDomProps } from "@/components/editor/common";
import { CellEditor } from "@/components/editor/cell/code/cell-editor";
import { LanguageToggles } from "@/components/editor/cell/code/language-toggle";
import { CellStatusComponent } from "@/components/editor/cell/CellStatus";
import { RunButton } from "@/components/editor/cell/RunButton";
import { StopButton } from "@/components/editor/cell/StopButton";
import { useRunCell } from "@/components/editor/cell/useRunCells";
import { Slide as CellOutputSlide } from "@/components/slides/slide";
import { maybeAddMarimoImport } from "@/core/cells/add-missing-import";
import { useCellActions } from "@/core/cells/cells";
import { autoInstantiateAtom, useUserConfig } from "@/core/config/config";
import {
  cellNeedsRun,
  cellStatusClasses,
  isUninstantiated,
} from "@/core/cells/utils";
import type { CellData, CellRuntimeState } from "@/core/cells/types";
import type { LanguageAdapterType } from "@/core/codemirror/language/types";
import { connectionAtom } from "@/core/network/connection";
import { useTheme } from "@/theme/useTheme";
import { cn } from "@/utils/cn";
import { ReadonlyCode } from "../editor/code/readonly-python-code";
import { getReadonlyCodeDisplay } from "@/core/cells/readonly-code-display";

type RuntimeCell = CellRuntimeState & CellData;

/**
 * Renders a single cell in the slides view as an editable CodeMirror editor
 * stacked with its output, mirroring the notebook layout. Editing and
 * Ctrl/Cmd+Enter run the cell against the live kernel so presenters can iterate
 * without leaving the slide deck.
 */
export const SlideCellView = ({ cell }: { cell: RuntimeCell }) => {
  const [userConfig] = useUserConfig();
  const { theme } = useTheme();
  const runCell = useRunCell(cell.id);
  const connection = useAtomValue(connectionAtom);
  const cellActions = useCellActions();
  const autoInstantiate = useAtomValue(autoInstantiateAtom);
  const editorViewRef = useRef<EditorView | null>(null);
  const editorViewParentRef = useRef<HTMLDivElement | null>(null);
  const [languageAdapter, setLanguageAdapter] = useState<
    LanguageAdapterType | undefined
  >();

  const afterToggleLanguage = useEvent(() => {
    maybeAddMarimoImport({
      autoInstantiate,
      createNewCell: cellActions.createNewCell,
    });
  });

  // Must be a stable identity: it feeds the editor's `extensions` memo
  const showHiddenCode = useEvent(() => undefined);

  const cellOutputPosition = userConfig.display.cell_output;
  const hasOutput = cell.output != null;

  const uninstantiated = isUninstantiated({
    executionTime: cell.runElapsedTimeMs ?? cell.lastExecutionTime,
    status: cell.status,
    errored: cell.errored,
    interrupted: cell.interrupted,
    stopped: cell.stopped,
  });

  const needsRun = cellNeedsRun({
    edited: cell.edited,
    interrupted: cell.interrupted,
    staleInputs: cell.staleInputs,
    disabled: cell.config.disabled,
    status: cell.status,
  });

  const editorWrapperClassName = cn(
    "marimo-cell",
    "hover-actions-parent",
    "interactive",
    cellStatusClasses({
      needsRun,
      errored: cell.errored,
      stopped: cell.stopped,
      disabled: cell.config.disabled,
      status: cell.status,
    }),
  );

  const output = (
    <CellOutputSlide
      cellId={cell.id}
      status={cell.status}
      output={cell.output}
    />
  );

  const toolbar = (
    <div className="absolute top-1 right-2 z-10 flex items-center gap-1.5">
      <CellStatusComponent
        editing={true}
        status={cell.status}
        disabled={cell.config.disabled ?? false}
        staleInputs={cell.staleInputs}
        edited={cell.edited}
        interrupted={cell.interrupted}
        elapsedTime={cell.runElapsedTimeMs ?? cell.lastExecutionTime}
        runStartTimestamp={cell.runStartTimestamp}
        lastRunStartTimestamp={cell.lastRunStartTimestamp}
        uninstantiated={uninstantiated}
      />
      <LanguageToggles
        code={cell.code}
        editorView={editorViewRef.current}
        currentLanguageAdapter={languageAdapter}
        onAfterToggle={afterToggleLanguage}
        className="flex items-center gap-1"
      />
      <div className="flex items-center shadow-none gap-1">
        <RunButton
          edited={cell.edited}
          status={cell.status}
          needsRun={needsRun}
          connectionState={connection.state}
          config={cell.config}
          onClick={runCell}
        />
        <StopButton status={cell.status} connectionState={connection.state} />
      </div>
    </div>
  );

  const editor = (
    <div
      tabIndex={-1}
      className={editorWrapperClassName}
      {...cellDomProps(cell.id, cell.name)}
    >
      <CellEditor
        theme={theme}
        showPlaceholder={false}
        id={cell.id}
        code={cell.code}
        config={cell.config}
        status={cell.status}
        serializedEditorState={cell.serializedEditorState}
        runCell={runCell}
        setEditorView={(ev) => {
          editorViewRef.current = ev;
        }}
        userConfig={userConfig}
        editorViewRef={editorViewRef}
        editorViewParentRef={editorViewParentRef}
        hasOutput={hasOutput}
        // hide_code is intentionally overridden in the slide view; the editor
        // is unmounted entirely when the user toggles code off.
        showHiddenCode={showHiddenCode}
        languageAdapter={languageAdapter}
        setLanguageAdapter={setLanguageAdapter}
        showLanguageToggles={false}
        // The reveal.js transforms in slides view break the inline AI
        // tooltip's fixed positioning, so disable it here.
        inlineAiTooltip={false}
        outputArea={cellOutputPosition}
        // Parent tooltips (completions, hover, signature help) to the Reveal
        // viewport so they stay visible when presenting fullscreen; `#App` sits
        // outside the fullscreened subtree and would never paint.
        tooltipParentSelector=".reveal-viewport"
      />
      {toolbar}
    </div>
  );

  return (
    <>
      {cellOutputPosition === "above" && output}
      {editor}
      {cellOutputPosition === "below" && output}
    </>
  );
};

export const SlideCellReadOnlyView = ({ cell }: { cell: RuntimeCell }) => {
  const [userConfig] = useUserConfig();
  const cellOutputPosition = userConfig.display.cell_output;

  const display = useMemo(() => getReadonlyCodeDisplay(cell.code), [cell.code]);

  const output = (
    <CellOutputSlide
      cellId={cell.id}
      status={cell.status}
      output={cell.output}
    />
  );

  const editor = (
    <div className="marimo-cell">
      <ReadonlyCode
        code={display.code}
        language={display.language}
        showHideCode={false}
      />
    </div>
  );

  return (
    <>
      {cellOutputPosition === "above" && output}
      {editor}
      {cellOutputPosition === "below" && output}
    </>
  );
};
