/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import {
  Check,
  Code2Icon,
  FolderDownIcon,
  ImageIcon,
  MoreHorizontalIcon,
} from "lucide-react";
import type React from "react";
import { memo, useRef, useState } from "react";
import { z } from "zod";
import { ReadonlyCode } from "@/components/editor/code/readonly-python-code";
import { OutputArea } from "@/components/editor/Output";
import { ConsoleOutput } from "@/components/editor/output/ConsoleOutput";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { outputIsLoading, outputIsStale } from "@/core/cells/cell";
import type { CellId } from "@/core/cells/ids";
import { isOutputEmpty } from "@/core/cells/outputs";
import type { CellData, CellRuntimeState } from "@/core/cells/types";
import { MarkdownLanguageAdapter } from "@/core/codemirror/language/languages/markdown";
import { useResolvedMarimoConfig } from "@/core/config/config";
import { KnownQueryParams } from "@/core/constants";
import type { OutputMessage } from "@/core/kernel/messages";
import { showCodeInRunModeAtom } from "@/core/meta/state";
import { isErrorMime } from "@/core/mime";
import { type AppMode, kioskModeAtom } from "@/core/mode";
import type { CellConfig } from "@/core/network/types";
import { downloadAsHTML } from "@/core/static/download-html";
import { isStaticNotebook } from "@/core/static/static-state";
import { isWasm } from "@/core/wasm/utils";
import { cn } from "@/utils/cn";
import { downloadHTMLAsImage } from "@/utils/download";
import { FloatingOutline } from "../../chrome/panels/outline/floating-outline";
import { cellDomProps } from "../../common";
import type { ICellRendererPlugin, ICellRendererProps } from "../types";
import { useDelayVisibility } from "./useDelayVisibility";
import { VerticalLayoutWrapper } from "./vertical-layout-wrapper";

type VerticalLayout = null;
type VerticalLayoutProps = ICellRendererProps<VerticalLayout>;

const VerticalLayoutRenderer: React.FC<VerticalLayoutProps> = ({
  cells,
  appConfig,
  mode,
}) => {
  const { invisible } = useDelayVisibility(cells.length, mode);
  const kioskMode = useAtomValue(kioskModeAtom);
  const [userConfig] = useResolvedMarimoConfig();
  const showCodeInRunModePreference = useAtomValue(showCodeInRunModeAtom);

  const urlParams = new URLSearchParams(window.location.search);
  const [showCode, setShowCode] = useState(() => {
    // Check if the setting was set in the mount options
    if (!showCodeInRunModePreference) {
      return false;
    }
    // If 'auto' or not found, use URL param
    // If url param is not set, we default to true for static notebooks, wasm notebooks, and kiosk mode
    const showCodeByQueryParam = urlParams.get(KnownQueryParams.showCode);
    return showCodeByQueryParam === null
      ? isStaticNotebook() || isWasm() || kioskMode
      : showCodeByQueryParam === "true";
  });

  const evaluateCanShowCode = () => {
    const cellsHaveCode = cells.some((cell) => Boolean(cell.code));

    if (kioskMode) {
      return true;
    }

    // Only show code if in read mode and there is at least one cell with code

    // If it is a static-notebook or wasm-read-only-notebook, code is always included,
    // but it can be turned it off via a query parameter (include-code=false)

    const includeCode = urlParams.get(KnownQueryParams.includeCode);
    return mode === "read" && includeCode !== "false" && cellsHaveCode;
  };

  const canShowCode = evaluateCanShowCode();

  const renderCell = (cell: CellRuntimeState & CellData) => {
    return (
      <VerticalCell
        key={cell.id}
        cellId={cell.id}
        output={cell.output}
        consoleOutputs={cell.consoleOutputs}
        status={cell.status}
        code={cell.code}
        config={cell.config}
        cellOutputArea={userConfig.display.cell_output}
        stopped={cell.stopped}
        showCode={showCode && canShowCode}
        errored={cell.errored}
        mode={mode}
        runStartTimestamp={cell.runStartTimestamp}
        interrupted={cell.interrupted}
        staleInputs={cell.staleInputs}
        name={cell.name}
        kiosk={kioskMode}
      />
    );
  };

  const renderCells = () => {
    if (appConfig.width === "columns") {
      const sortedColumns = groupCellsByColumn(cells);
      return (
        <div className="flex flex-row gap-8 w-full">
          {sortedColumns.map(([columnIndex, columnCells]) => (
            <div
              key={columnIndex}
              className="flex-1 flex flex-col gap-2 w-contentWidth"
            >
              {columnCells.map(renderCell)}
            </div>
          ))}
        </div>
      );
    }

    if (cells.length === 0 && !invisible) {
      return (
        <div className="flex-1 flex flex-col items-center justify-center py-8">
          <Alert variant="info">
            <AlertTitle>Empty Notebook</AlertTitle>
            <AlertDescription>
              This notebook has no code or outputs.
            </AlertDescription>
          </Alert>
        </div>
      );
    }

    return <>{cells.map(renderCell)}</>;
  };

  // in read mode (required for canShowCode to be true), we need to insert
  // spacing between cells to prevent them from colliding; in edit mode,
  // spacing is handled elsewhere
  return (
    <VerticalLayoutWrapper invisible={invisible} appConfig={appConfig}>
      {showCode && canShowCode ? (
        <div className="flex flex-col gap-5"> {renderCells()}</div>
      ) : (
        renderCells()
      )}
      {mode === "read" && (
        <ActionButtons
          canShowCode={canShowCode}
          showCode={showCode}
          onToggleShowCode={() => setShowCode((v) => !v)}
        />
      )}
      <FloatingOutline />
    </VerticalLayoutWrapper>
  );
};

const ActionButtons: React.FC<{
  canShowCode: boolean;
  showCode: boolean;
  onToggleShowCode: () => void;
}> = ({ canShowCode, showCode, onToggleShowCode }) => {
  const handleDownloadAsPNG = async () => {
    const app = document.getElementById("App");
    if (!app) {
      return;
    }
    await downloadHTMLAsImage(app, document.title);
  };

  const handleDownloadAsHTML = async () => {
    const app = document.getElementById("App");
    if (!app) {
      return;
    }
    await downloadAsHTML({ filename: document.title, includeCode: true });
  };

  const isStatic = isStaticNotebook();
  const actions: React.ReactNode[] = [];

  if (canShowCode) {
    actions.push(
      <DropdownMenuItem
        onSelect={onToggleShowCode}
        id="notebook-action-show-code"
        key="show-code"
      >
        <Code2Icon className="mr-2" size={14} strokeWidth={1.5} />
        <span className="flex-1">Show code</span>
        {showCode && <Check className="h-4 w-4" />}
      </DropdownMenuItem>,
      <DropdownMenuSeparator key="show-code-separator" />,
    );
  }

  if (!isStatic) {
    actions.push(
      <DropdownMenuItem
        onSelect={handleDownloadAsHTML}
        id="notebook-action-download-html"
        key="download-html"
      >
        <FolderDownIcon className="mr-2" size={14} strokeWidth={1.5} />
        Download as HTML
      </DropdownMenuItem>,
      <DropdownMenuSeparator key="download-html-separator" />,
      <DropdownMenuItem
        onSelect={handleDownloadAsPNG}
        id="notebook-action-download-png"
        key="download-png"
      >
        <ImageIcon className="mr-2" size={14} strokeWidth={1.5} />
        Download as PNG
      </DropdownMenuItem>,
    );
  }

  if (actions.length === 0) {
    return null;
  }

  // Don't change the id of this element
  // as this may be used in custom css to hide/show the actions dropdown
  return (
    <div
      id="notebook-actions-dropdown"
      className={cn(
        "right-0 top-0 z-50 m-4 no-print flex gap-2 print:hidden",
        // If the notebook is static, we have a banner at the top, so
        // we can't use fixed positioning. Ideally this is sticky, but the
        // current dom structure makes that difficult.
        isStaticNotebook() ? "absolute" : "fixed",
      )}
    >
      <DropdownMenu modal={false}>
        <DropdownMenuTrigger asChild={true}>
          <Button variant="secondary" size="xs">
            <MoreHorizontalIcon className="w-4 h-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="no-print w-[220px]">
          {actions}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
};

interface VerticalCellProps
  extends Pick<
    CellRuntimeState,
    | "output"
    | "consoleOutputs"
    | "status"
    | "stopped"
    | "errored"
    | "interrupted"
    | "staleInputs"
    | "runStartTimestamp"
  > {
  cellOutputArea: "above" | "below";
  cellId: CellId;
  config: CellConfig;
  code: string;
  mode: AppMode;
  showCode: boolean;
  name: string;
  kiosk: boolean;
}

const VerticalCell = memo(
  ({
    output,
    consoleOutputs,
    cellOutputArea,
    cellId,
    status,
    stopped,
    errored,
    config,
    interrupted,
    staleInputs,
    runStartTimestamp,
    code,
    showCode,
    mode,
    name,
    kiosk,
  }: VerticalCellProps) => {
    const cellRef = useRef<HTMLDivElement>(null);

    const outputStale = outputIsStale(
      {
        status,
        output,
        interrupted,
        runStartTimestamp,
        staleInputs,
      },
      false,
    );
    const loading = outputIsLoading(status);

    // Kiosk and not presenting
    const kioskFull = kiosk && mode !== "present";

    const isPureMarkdown = new MarkdownLanguageAdapter().isSupported(code);
    const published = !showCode && !kioskFull;
    const className = cn(
      "marimo-cell",
      "hover-actions-parent empty:invisible",
      {
        published: published,
        interactive: mode === "edit",
        "has-error": errored,
        stopped: stopped,
        borderless: isPureMarkdown && !published,
      },
    );

    // Read mode and show code
    if ((mode === "read" && showCode) || kioskFull) {
      const outputArea = (
        <OutputArea
          allowExpand={true}
          output={output}
          className="output-area"
          cellId={cellId}
          stale={outputStale}
          loading={loading}
        />
      );

      // Hide the code if it's pure markdown and there's an output, or if the code is empty
      const hideCode = shouldHideCode(code, output);

      return (
        <div
          tabIndex={-1}
          ref={cellRef}
          className={className}
          {...cellDomProps(cellId, name)}
        >
          {cellOutputArea === "above" && outputArea}
          {!hideCode && (
            <div className="tray">
              <ReadonlyCode
                initiallyHideCode={config.hide_code || kiosk}
                code={code}
              />
            </div>
          )}
          {cellOutputArea === "below" && outputArea}
          <ConsoleOutput
            consoleOutputs={consoleOutputs}
            stale={outputStale}
            cellName={name}
            onSubmitDebugger={() => null}
            cellId={cellId}
            debuggerActive={false}
          />
        </div>
      );
    }

    const outputIsError = isErrorMime(output?.mimetype);
    const hidden = errored || interrupted || stopped || outputIsError;
    if (hidden) {
      return null;
    }

    return (
      <div
        tabIndex={-1}
        ref={cellRef}
        className={className}
        {...cellDomProps(cellId, name)}
      >
        <OutputArea
          allowExpand={mode === "edit"}
          output={output}
          className="output-area"
          cellId={cellId}
          stale={outputStale}
          loading={loading}
        />
      </div>
    );
  },
);
VerticalCell.displayName = "VerticalCell";

export const VerticalLayoutPlugin: ICellRendererPlugin<
  VerticalLayout,
  VerticalLayout
> = {
  type: "vertical",
  name: "Vertical",
  validator: z.any(),
  Component: VerticalLayoutRenderer,
  deserializeLayout: (serialized) => serialized,
  serializeLayout: (layout) => layout,
  getInitialLayout: () => null,
};

export function groupCellsByColumn(
  cells: Array<CellRuntimeState & CellData>,
): Array<[number, Array<CellRuntimeState & CellData>]> {
  // Group cells by column
  const cellsByColumn = new Map<number, Array<CellRuntimeState & CellData>>();
  let lastSeenColumn = 0;
  cells.forEach((cell) => {
    const column = cell.config.column ?? lastSeenColumn;
    lastSeenColumn = column;
    if (!cellsByColumn.has(column)) {
      cellsByColumn.set(column, []);
    }
    cellsByColumn.get(column)?.push(cell);
  });

  // Sort columns by index
  return [...cellsByColumn.entries()].sort(([a], [b]) => a - b);
}

/**
 * Determine if the code should be hidden.
 *
 * This is used to hide the code if it's pure markdown and there's an output,
 * or if the code is empty.
 */
export function shouldHideCode(code: string, output: OutputMessage | null) {
  const isPureMarkdown = new MarkdownLanguageAdapter().isSupported(code);
  const hasOutput = output !== null && !isOutputEmpty(output);
  return (isPureMarkdown && hasOutput) || code.trim() === "";
}
