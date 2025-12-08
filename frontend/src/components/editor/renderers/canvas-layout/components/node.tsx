/* Copyright 2024 Marimo. All rights reserved. */

import type { EditorView } from "@codemirror/view";
import {
  Handle,
  type Node,
  type NodeProps,
  NodeResizer,
  Position,
  useReactFlow,
} from "@xyflow/react";
import { useAtomValue, useSetAtom } from "jotai";
import {
  AlertCircleIcon,
  ChevronDownIcon,
  MoreHorizontalIcon,
} from "lucide-react";
import React, {
  memo,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import useEvent from "react-use-event-hook";
import {
  CellActionsDropdown,
  type CellActionsDropdownHandle,
} from "@/components/editor/cell/cell-actions";
import { CellEditor } from "@/components/editor/cell/code/cell-editor";
import { RunButton } from "@/components/editor/cell/RunButton";
import { StopButton } from "@/components/editor/cell/StopButton";
import { Toolbar, ToolbarItem } from "@/components/editor/cell/toolbar";
import { useRunCell } from "@/components/editor/cell/useRunCells";
import {
  type OnRefactorWithAI,
  OutputRenderer,
} from "@/components/editor/Output";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { maybeAddMarimoImport } from "@/core/cells/add-missing-import";
import { outputIsLoading, outputIsStale } from "@/core/cells/cell";
import {
  useCellActions,
  useCellData,
  useCellHandle,
  useCellRuntime,
} from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { isOutputEmpty } from "@/core/cells/outputs";
import { switchLanguage } from "@/core/codemirror/language/extension";
import { LanguageAdapters } from "@/core/codemirror/language/LanguageAdapters";
import type { LanguageAdapterType } from "@/core/codemirror/language/types";
import { autoInstantiateAtom, useUserConfig } from "@/core/config/config";
import type { AppConfig } from "@/core/config/config-schema";
import { connectionAtom } from "@/core/network/connection";
import { isAppConnected } from "@/core/websocket/connection-utils";
import { useResizeObserver } from "@/hooks/useResizeObserver";
import { cn } from "@/utils/cn";
import { derefNotNull } from "@/utils/dereference";
import { formatTime } from "@/utils/formatting";
import { Functions } from "@/utils/functions";
import type { CanvasNodeData, DataFlowDirection } from "../models";
import { canvasSettingsAtom } from "../state";
import { AddCellButtons } from "./add-cell-buttons";
import { useNodeAutoResize } from "./useNodeAutoResize";
import "./node.css";
import { cellDomProps } from "@/components/editor/common";
import { ConsoleOutput } from "@/components/editor/output/console/ConsoleOutput";
import { TooltipProvider } from "@/components/ui/tooltip";
import { aiCompletionCellAtom } from "@/core/ai/state";
import { isErrorMime } from "@/core/mime";
import { useRequestClient } from "@/core/network/requests";

// Constants
const AVAILABLE_LANGUAGES: Array<{
  value: LanguageAdapterType;
  label: string;
}> = [
  { value: "python", label: "Python" },
  { value: "markdown", label: "Markdown" },
  { value: "sql", label: "SQL" },
] as const;

const NODE_RESIZER_CONFIG = {
  minWidth: 200,
  handleClassName: "!w-2 !h-2 !border-1 !border-primary !bg-background",
  lineClassName: "!border-primary",
} as const;

interface CellNodeProps extends Partial<NodeProps<Node<CanvasNodeData>>> {
  data: CanvasNodeData;
  selected?: boolean;
  appConfig: AppConfig;
  isEditable: boolean;
  dataFlow?: DataFlowDirection;
}

/**
 * Canvas cell toolbar component
 * Floating toolbar between editor and output
 */
const CanvasCellToolbar: React.FC<{
  cellId: CellId;
  editorView: React.RefObject<EditorView | null>;
}> = memo(({ cellId, editorView }) => {
  const cellData = useCellData(cellId);
  const cellRuntime = useCellRuntime(cellId);
  const runCell = useRunCell(cellId);
  const connection = useAtomValue(connectionAtom);
  const cellActionDropdownRef = useRef<CellActionsDropdownHandle>(null);

  const isConnected = isAppConnected(connection.state);
  const needsRun =
    cellData.edited ||
    cellRuntime.interrupted ||
    (cellRuntime.staleInputs && !cellData.config.disabled);
  const hasOutput = cellRuntime.output !== undefined;
  const hasConsoleOutput = cellRuntime.consoleOutputs.length > 0;
  const running = cellRuntime.status === "running";

  const getEditorView = () => editorView.current;

  return (
    <div className="absolute -top-4 right-2 z-[301]">
      <Toolbar
        className={cn(
          "bg-transparent",
          // Show the toolbar on hover, or when the cell needs to be run
          // !needsRun && "hover-action",
        )}
      >
        {!running && (
          <RunButton
            edited={cellData.edited}
            onClick={isConnected ? runCell : Functions.NOOP}
            connectionState={connection.state}
            status={cellRuntime.status}
            config={cellData.config}
            needsRun={needsRun}
          />
        )}
        {running && (
          <StopButton
            delayMs={0}
            status={cellRuntime.status}
            connectionState={connection.state}
            className="bg-background"
          />
        )}
        <CellActionsDropdown
          ref={cellActionDropdownRef}
          cellId={cellId}
          status={cellRuntime.status}
          getEditorView={getEditorView}
          name={cellData.name}
          config={cellData.config}
          hasOutput={hasOutput}
          hasConsoleOutput={hasConsoleOutput}
        >
          <ToolbarItem
            variant={"green"}
            tooltip={null}
            data-testid="cell-actions-button"
          >
            <MoreHorizontalIcon strokeWidth={1.5} />
          </ToolbarItem>
        </CellActionsDropdown>
      </Toolbar>
    </div>
  );
});

CanvasCellToolbar.displayName = "CanvasCellToolbar";

/**
 * Connected cell editor component
 * Manages the code editor for a canvas cell
 */
const ConnectedCellEditor: React.FC<{
  cellId: CellId;
  editorView: React.RefObject<EditorView | null>;
  editorViewParentRef: React.RefObject<HTMLDivElement | null>;
  languageAdapter: LanguageAdapterType | undefined;
  setLanguageAdapter: React.Dispatch<
    React.SetStateAction<LanguageAdapterType | undefined>
  >;
  onHeightChange?: (height: number) => void;
}> = memo(
  ({
    cellId,
    editorView,
    editorViewParentRef,
    languageAdapter,
    setLanguageAdapter,
    onHeightChange,
  }) => {
    const [userConfig] = useUserConfig();
    const cellData = useCellData(cellId);
    const cellRuntime = useCellRuntime(cellId);
    const runCell = useRunCell(cellId);
    const containerRef = useRef<HTMLDivElement>(null);

    // Track editor height changes
    useResizeObserver({
      ref: containerRef,
      onResize: (size) => {
        if (size.height && onHeightChange) {
          onHeightChange(size.height);
        }
      },
    });

    return (
      <div ref={containerRef} className="w-full relative">
        <div className="overflow-hidden rounded-t-lg">
          <CellEditor
            theme="light"
            showPlaceholder={false}
            id={cellId}
            code={cellData.code}
            config={cellData.config}
            status={cellRuntime.status}
            serializedEditorState={cellData.serializedEditorState}
            runCell={runCell}
            setEditorView={(ev) => {
              editorView.current = ev;
            }}
            userConfig={userConfig}
            editorViewRef={editorView}
            editorViewParentRef={editorViewParentRef}
            hidden={false}
            hasOutput={cellRuntime.output !== undefined}
            showHiddenCode={Functions.NOOP}
            languageAdapter={languageAdapter}
            setLanguageAdapter={setLanguageAdapter}
            showLanguageToggles={false}
          />
        </div>
        {/* Floating Toolbar */}
        <CanvasCellToolbar cellId={cellId} editorView={editorView} />
      </div>
    );
  },
);

ConnectedCellEditor.displayName = "ConnectedCellEditor";

/**
 * Connected cell output component
 * Renders the output area for a canvas cell
 */
const ConnectedCellOutput: React.FC<{
  cellId: CellId;
}> = memo(({ cellId }) => {
  const cellData = useCellData(cellId);
  const cellRuntime = useCellRuntime(cellId);

  const loading = outputIsLoading(cellRuntime.status);
  const stale = outputIsStale(cellRuntime, cellData.edited);

  if (cellRuntime.output === null || isOutputEmpty(cellRuntime.output)) {
    return null;
  }

  return (
    <div
      className={cn(
        "border-t",
        stale && "marimo-output-stale",
        loading && "marimo-output-loading",
        "marimo-output marimo-canvas-output",
      )}
    >
      <OutputRenderer cellId={cellId} message={cellRuntime.output} />
    </div>
  );
});

ConnectedCellOutput.displayName = "ConnectedCellOutput";

/**
 * Canvas cell footer component
 * Shows language selector dropdown, elapsed time, and console errors popover
 */
const CanvasCellFooter: React.FC<{
  cellId: CellId;
  languageAdapter: LanguageAdapterType | undefined;
  editorView: React.RefObject<EditorView | null>;
  code: string;
  onRefactorWithAI: OnRefactorWithAI;
}> = memo(({ cellId, languageAdapter, editorView, code, onRefactorWithAI }) => {
  const cellRuntime = useCellRuntime(cellId);
  const cellActions = useCellActions();
  const autoInstantiate = useAtomValue(autoInstantiateAtom);
  const cellData = useCellData(cellId);
  const { sendStdin } = useRequestClient();
  const hasConsoleOutputs = cellRuntime.consoleOutputs.length > 0;

  const language =
    languageAdapter === "markdown"
      ? "Markdown"
      : languageAdapter === "sql"
        ? "SQL"
        : "Python";

  const elapsedTimeMs = cellRuntime.runElapsedTimeMs;
  const elapsedTimeSeconds = elapsedTimeMs ? elapsedTimeMs / 1000 : null;

  const afterToggleMarkdown = useEvent(() => {
    maybeAddMarimoImport({
      autoInstantiate,
      createNewCell: cellActions.createNewCell,
    });
  });

  const handleLanguageChange = useEvent((newLanguage: LanguageAdapterType) => {
    if (!editorView.current) {
      return;
    }

    // Check if the target language supports the current code
    const adapter = LanguageAdapters[newLanguage];
    const isSupported = adapter.isSupported(code) || code.trim() === "";

    // If not supported, keep code as-is; otherwise transform it
    switchLanguage(editorView.current, {
      language: newLanguage,
      keepCodeAsIs: !isSupported,
    });

    if (newLanguage === "markdown" || newLanguage === "sql") {
      afterToggleMarkdown();
    }
  });

  // Always show dropdown since we have multiple language options
  const showDropdown = true;

  return (
    <div className="w-full border-t px-2 py-1 flex items-center justify-between text-xs text-muted-foreground bg-muted/30 h-[28px] z-10">
      <div className="flex items-center gap-1.5">
        {showDropdown ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild={true}>
              <button
                className="flex items-center gap-1 px-1.5 py-0.5 rounded hover:bg-muted font-medium outline-none focus:ring-1 focus:ring-ring"
                type="button"
              >
                {language}
                <ChevronDownIcon className="w-3 h-3" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" side="top">
              {AVAILABLE_LANGUAGES.map((lang) => (
                <DropdownMenuItem
                  key={lang.value}
                  onClick={() => handleLanguageChange(lang.value)}
                  disabled={lang.value === languageAdapter}
                >
                  {lang.label}
                  {lang.value === languageAdapter && (
                    <span className="ml-auto text-[10px]">✓</span>
                  )}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        ) : (
          <span className="font-medium">{language}</span>
        )}

        {/* Console Output Popover */}
        {hasConsoleOutputs && (
          <Popover>
            <PopoverTrigger asChild={true}>
              <button
                className="flex items-center gap-1 px-1.5 py-0.5 rounded hover:bg-muted outline-none focus:ring-1 focus:ring-ring text-destructive"
                type="button"
                title="Console output"
              >
                <AlertCircleIcon className="w-3.5 h-3.5" />
              </button>
            </PopoverTrigger>
            <PopoverContent
              align="start"
              side="top"
              className="w-[600px] p-0"
              scrollable={true}
            >
              <ConsoleOutput
                consoleOutputs={cellRuntime.consoleOutputs}
                stale={outputIsStale(cellRuntime, cellData.edited)}
                cellName={cellData.name}
                onRefactorWithAI={onRefactorWithAI}
                onClear={() => {
                  cellActions.clearCellConsoleOutput({ cellId });
                }}
                onSubmitDebugger={(text, index) => {
                  cellActions.setStdinResponse({
                    cellId,
                    response: text,
                    outputIndex: index,
                  });
                  sendStdin({ text });
                }}
                cellId={cellId}
                debuggerActive={cellRuntime.debuggerActive}
                className="border-none rounded-none"
              />
            </PopoverContent>
          </Popover>
        )}
      </div>
      {elapsedTimeSeconds !== null && (
        <span className="font-mono">
          {formatTime(elapsedTimeSeconds, navigator.language)}
        </span>
      )}
    </div>
  );
});

CanvasCellFooter.displayName = "CanvasCellFooter";

/**
 * Canvas cell node component
 * Renders a marimo cell within a react-flow node
 */
const CellNodeComponent: React.FC<CellNodeProps> = ({
  data,
  selected,
  isEditable,
  id,
  dataFlow = "left-right",
  positionAbsoluteX,
  positionAbsoluteY,
  width,
  height,
}) => {
  // biome-ignore lint/suspicious/noConsole: For debugging
  console.count("CellNode rendered");
  const cellRuntime = useCellRuntime(data.cellId);
  const cellData = useCellData(data.cellId);
  const setAiCompletionCell = useSetAtom(aiCompletionCellAtom);
  const hasOutput = !isOutputEmpty(cellRuntime.output);
  const canvasSettings = useAtomValue(canvasSettingsAtom);
  const { fitView } = useReactFlow();
  const hasError =
    cellRuntime.errored ||
    isErrorMime(cellRuntime.output?.mimetype) ||
    cellRuntime.consoleOutputs.some((output) => isErrorMime(output.mimetype));

  const editorView = useRef<EditorView | null>(null);
  const editorViewParentRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [languageAdapter, setLanguageAdapter] = useState<LanguageAdapterType>();
  const [editorHeight, setEditorHeight] = useState<number>(0);

  // Auto-resize hook handles all output-based resizing logic
  const {
    outputRef,
    totalHeight,
    handleResizeStart,
    handleResize,
    handleResizeEnd,
    handleLanguageChange,
    handleConsoleOutputChange,
    triggerResize,
    minOutputHeight,
    footerHeight,
  } = useNodeAutoResize({
    nodeId: id,
    hasOutput,
    editorHeight,
  });

  // Register cell handle so delete operations can access the editor state
  const cellHandleRef = useCellHandle(data.cellId);
  useImperativeHandle(
    cellHandleRef,
    () => ({
      get editorView() {
        return derefNotNull(editorView);
      },
      get editorViewOrNull() {
        return editorView.current;
      },
    }),
    [editorView],
  );

  const handleEditorHeightChange = (height: number) => {
    setEditorHeight(height);
  };

  const handleRefactorWithAI: OnRefactorWithAI = useEvent(
    (opts: { prompt: string; triggerImmediately: boolean }) => {
      setAiCompletionCell({
        cellId: data.cellId,
        initialPrompt: opts.prompt,
        triggerImmediately: opts.triggerImmediately,
      });
    },
  );

  const handleDoubleClick = useEvent((e: React.MouseEvent) => {
    // Prevent event from bubbling to prevent unwanted interactions
    e.stopPropagation();

    if (id) {
      // Trigger resize to recalculate dimensions based on content
      triggerResize();

      // Small delay to let resize complete before zooming
      setTimeout(() => {
        // Zoom to this node with some padding
        fitView({
          nodes: [{ id }],
          duration: 400,
          padding: 0.3,
          maxZoom: 1.5,
        });
      }, 100);
    }
  });

  // Track language adapter changes and trigger resize
  const prevLanguageRef = useRef<LanguageAdapterType | undefined>(
    languageAdapter,
  );
  useEffect(() => {
    // Only trigger on actual language changes, not initial mount
    if (
      prevLanguageRef.current !== undefined &&
      prevLanguageRef.current !== languageAdapter
    ) {
      handleLanguageChange();
    }
    prevLanguageRef.current = languageAdapter;
  }, [languageAdapter, handleLanguageChange]);

  // Track console output changes and trigger resize
  const prevConsoleCountRef = useRef<number>(cellRuntime.consoleOutputs.length);
  useEffect(() => {
    const currentCount = cellRuntime.consoleOutputs.length;
    if (prevConsoleCountRef.current !== currentCount) {
      handleConsoleOutputChange();
    }
    prevConsoleCountRef.current = currentCount;
  }, [cellRuntime.consoleOutputs.length, handleConsoleOutputChange]);

  if (!cellData) {
    return (
      <div className="w-full h-full flex items-center justify-center text-muted-foreground">
        Cell not found
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      {...cellDomProps(data.cellId, cellData.name)}
      onDoubleClick={handleDoubleClick}
      className={cn(
        "group w-full h-full rounded-lg border border-input/80 shadow-sm bg-background flex flex-col relative hover-actions-parent",
        selected && "ring-1 ring-primary/80",
        hasError && "border-destructive/80",
        isEditable && "cursor-move",
      )}
    >
      {/* Handles for connections (hidden via CSS) */}
      <Handle
        type="target"
        position={dataFlow === "left-right" ? Position.Left : Position.Top}
      />
      <Handle
        type="source"
        position={dataFlow === "left-right" ? Position.Right : Position.Bottom}
      />

      {/* Cell Editor */}
      <TooltipProvider>
        {isEditable && (
          <ConnectedCellEditor
            cellId={data.cellId}
            editorView={editorView}
            editorViewParentRef={editorViewParentRef}
            languageAdapter={languageAdapter}
            setLanguageAdapter={setLanguageAdapter}
            onHeightChange={handleEditorHeightChange}
          />
        )}

        {/* Output Area - only show if there's output */}
        {hasOutput && (
          <div
            ref={outputRef}
            className="w-full overflow-auto flex-1"
            style={{
              minHeight: `${minOutputHeight}px`,
            }}
          >
            <ConnectedCellOutput cellId={data.cellId} />
          </div>
        )}

        {/* Footer */}
        <CanvasCellFooter
          cellId={data.cellId}
          languageAdapter={languageAdapter}
          editorView={editorView}
          code={cellData.code}
          onRefactorWithAI={handleRefactorWithAI}
        />
      </TooltipProvider>

      {/* Add cell buttons */}
      {isEditable && (
        <AddCellButtons
          cellId={data.cellId}
          nodePosition={
            positionAbsoluteX !== undefined && positionAbsoluteY !== undefined
              ? { x: positionAbsoluteX, y: positionAbsoluteY }
              : undefined
          }
          nodeSize={
            width !== undefined && height !== undefined
              ? { width, height }
              : undefined
          }
        />
      )}

      {/* Node resizer */}
      {isEditable && id && (
        <NodeResizer
          nodeId={id}
          isVisible={selected}
          minWidth={NODE_RESIZER_CONFIG.minWidth}
          onResizeStart={handleResizeStart}
          onResize={handleResize}
          onResizeEnd={handleResizeEnd}
          {...(hasOutput
            ? {
                // With output: allow both horizontal and vertical resize
                minHeight: minOutputHeight + editorHeight + footerHeight,
              }
            : {
                // Without output: lock height to prevent vertical resize
                minHeight: totalHeight,
                maxHeight: totalHeight,
              })}
          handleClassName={NODE_RESIZER_CONFIG.handleClassName}
          lineClassName={NODE_RESIZER_CONFIG.lineClassName}
        />
      )}

      {/* Debug info - show dimensions */}
      {canvasSettings.debug && width !== undefined && height !== undefined && (
        <div className="absolute font-bold -bottom-6 right-0 px-2 py-1 text-xs pointer-events-none z-50">
          (w: {Math.round(width)}, h: {Math.round(height)})
        </div>
      )}
    </div>
  );
};

export const CellNode = memo(CellNodeComponent);
CellNode.displayName = "CellNode";
