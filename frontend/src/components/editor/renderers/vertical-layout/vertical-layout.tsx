/* Copyright 2024 Marimo. All rights reserved. */
import type React from "react";
import { memo, useRef, useState } from "react";
import type { CellRuntimeState } from "@/core/cells/types";
import { type CellId, HTMLCellId } from "@/core/cells/ids";
import { OutputArea } from "@/components/editor/Output";
import type { ICellRendererPlugin, ICellRendererProps } from "../types";
import { VerticalLayoutWrapper } from "./vertical-layout-wrapper";
import { z } from "zod";
import { useDelayVisibility } from "./useDelayVisibility";
import { type AppMode, kioskModeAtom } from "@/core/mode";
import { ReadonlyCode } from "@/components/editor/code/readonly-python-code";
import {
  Check,
  Code2Icon,
  FolderDownIcon,
  ImageIcon,
  MoreHorizontalIcon,
} from "lucide-react";
import { cn } from "@/utils/cn";
import { Button } from "@/components/ui/button";
import { outputIsStale } from "@/core/cells/cell";
import { isStaticNotebook } from "@/core/static/static-state";
import { ConsoleOutput } from "@/components/editor/output/ConsoleOutput";
import {
  DropdownMenuItem,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { downloadHTMLAsImage } from "@/utils/download";
import { downloadAsHTML } from "@/core/static/download-html";
import { isWasm } from "@/core/wasm/utils";
import type { CellConfig } from "@/core/network/types";
import { useAtomValue } from "jotai";
import { FloatingOutline } from "../../chrome/panels/outline/floating-outline";
import { KnownQueryParams } from "@/core/constants";
import { useUserConfig } from "@/core/config/config";
import { MarkdownLanguageAdapter } from "@/core/codemirror/language/markdown";
import { isErrorMime } from "@/core/mime";

type VerticalLayout = null;
type VerticalLayoutProps = ICellRendererProps<VerticalLayout>;

const VerticalLayoutRenderer: React.FC<VerticalLayoutProps> = ({
  cells,
  appConfig,
  mode,
}) => {
  const { invisible } = useDelayVisibility(cells.length, mode);
  const kioskMode = useAtomValue(kioskModeAtom);
  const [userConfig] = useUserConfig();

  const urlParams = new URLSearchParams(window.location.search);
  const showCodeDefault = urlParams.get(KnownQueryParams.showCode);
  const [showCode, setShowCode] = useState(() => {
    // Default to showing code if the notebook is static or wasm
    return showCodeDefault === null
      ? isStaticNotebook() || isWasm() || kioskMode
      : showCodeDefault === "true";
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

  const verticalCells = (
    <>
      {cells.map((cell) => (
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
      ))}
    </>
  );

  // in read mode (required for canShowCode to be true), we need to insert
  // spacing between cells to prevent them from colliding; in edit mode,
  // spacing is handled elsewhere
  return (
    <VerticalLayoutWrapper invisible={invisible} appConfig={appConfig}>
      {showCode && canShowCode ? (
        <div className="flex flex-col gap-5"> {verticalCells}</div>
      ) : (
        verticalCells
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

  return (
    <div
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
          {canShowCode && (
            <>
              <DropdownMenuItem onSelect={onToggleShowCode}>
                <Code2Icon className="mr-2" size={14} strokeWidth={1.5} />
                <span className="flex-1">Show code</span>
                {showCode && <Check className="h-4 w-4" />}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
            </>
          )}
          <DropdownMenuItem onSelect={handleDownloadAsHTML}>
            <FolderDownIcon className="mr-2" size={14} strokeWidth={1.5} />
            Download as HTML
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={handleDownloadAsPNG}>
            <ImageIcon className="mr-2" size={14} strokeWidth={1.5} />
            Download as PNG
          </DropdownMenuItem>
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

    // Kiosk and not presenting
    const kioskFull = kiosk && mode !== "present";

    const className = cn("Cell", "hover-actions-parent", {
      published: !showCode && !kioskFull,
      interactive: mode === "edit",
      "has-error": errored,
      stopped: stopped,
    });

    const HTMLId = HTMLCellId.create(cellId);

    // Read mode and show code
    if ((mode === "read" && showCode) || kioskFull) {
      const outputArea = (
        <OutputArea
          allowExpand={true}
          output={output}
          className="output-area"
          cellId={cellId}
          stale={outputStale}
        />
      );

      const isCodeEmpty = code.trim() === "";
      const isPureMarkdown = new MarkdownLanguageAdapter().isSupported(code);

      return (
        <div tabIndex={-1} id={HTMLId} ref={cellRef} className={className}>
          {cellOutputArea === "above" && outputArea}
          {/* Hide code if it's empty or pure markdown */}
          {!isPureMarkdown && !isCodeEmpty && (
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
      <div tabIndex={-1} id={HTMLId} ref={cellRef} className={className}>
        <OutputArea
          allowExpand={mode === "edit"}
          output={output}
          className="output-area"
          cellId={cellId}
          stale={outputStale}
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
