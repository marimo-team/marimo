/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { memo, useEffect, useMemo, useRef, useState } from "react";

import type { OutputMessage } from "@/core/kernel/messages";

import { logNever } from "../../utils/assertNever";
import { JsonOutput } from "./output/JsonOutput";
import { HtmlOutput } from "./output/HtmlOutput";
import { ImageOutput } from "./output/ImageOutput";
import { MarimoErrorOutput } from "./output/MarimoErrorOutput";
import { TextOutput } from "./output/TextOutput";
import { VideoOutput } from "./output/VideoOutput";
import { CellOutputId, type CellId } from "@/core/cells/ids";
import { cn } from "@/utils/cn";
import { ErrorBoundary } from "./boundary/ErrorBoundary";

import "./output/Outputs.css";
import { Button } from "../ui/button";
import {
  ChevronsDownUpIcon,
  ChevronsUpDownIcon,
  ExpandIcon,
} from "lucide-react";
import { Tooltip } from "../ui/tooltip";
import { useExpandedOutput } from "@/core/cells/outputs";
import { invariant } from "@/utils/invariant";
import { CsvViewer } from "./file-tree/renderers";
import { LazyAnyLanguageCodeMirror } from "@/plugins/impl/code/LazyAnyLanguageCodeMirror";
import { MarimoTracebackOutput } from "./output/MarimoTracebackOutput";
import { useTheme } from "@/theme/useTheme";
import { renderHTML } from "@/plugins/core/RenderHTML";
import type { TopLevelFacetedUnitSpec } from "@/plugins/impl/data-explorer/queries/types";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../ui/tabs";
import { Objects } from "@/utils/objects";
import { renderMimeIcon } from "./renderMimeIcon";
import { Events } from "@/utils/events";

const LazyVegaLite = React.lazy(() =>
  import("react-vega").then((m) => ({ default: m.VegaLite })),
);

type MimeBundle = Record<OutputMessage["mimetype"], { [key: string]: unknown }>;
type MimeBundleOrTuple = MimeBundle | [MimeBundle, { [key: string]: unknown }];

/**
 * Renders an output based on an OutputMessage.
 */
export const OutputRenderer: React.FC<{
  message: Pick<OutputMessage, "channel" | "data" | "mimetype">;
  cellId?: CellId;
  onRefactorWithAI?: (opts: { prompt: string }) => void;
}> = memo((props) => {
  const { message, onRefactorWithAI, cellId } = props;
  const { theme } = useTheme();

  // Memoize parsing the json data
  const parsedJsonData = useMemo(() => {
    const data = message.data;
    switch (message.mimetype) {
      case "application/json":
      case "application/vnd.marimo+mimebundle":
      case "application/vnd.vegalite.v5+json":
      case "application/vnd.vega.v5+json":
        return typeof data === "string" ? JSON.parse(data) : data;
      default:
        return;
    }
  }, [message.mimetype, message.data]);

  const { channel, data, mimetype } = message;

  if (data == null) {
    return null;
  }

  // TODO(akshayka): audio; pdf; text/csv; excel?; text/css; text/javascript
  switch (mimetype) {
    case "text/html":
      invariant(
        typeof data === "string",
        `Expected string data for mime=${mimetype}. Got ${typeof data}`,
      );
      return <HtmlOutput className={channel} html={data} />;

    case "text/plain":
      invariant(
        typeof data === "string",
        `Expected string data for mime=${mimetype}. Got ${typeof data}`,
      );
      return <TextOutput channel={channel} text={data} />;

    case "application/json":
      // TODO: format is 'auto', but should make configurable once cells can
      // support config
      return (
        <JsonOutput className={channel} data={parsedJsonData} format="auto" />
      );
    case "image/png":
    case "image/tiff":
    case "image/avif":
    case "image/bmp":
    case "image/gif":
    case "image/jpeg":
      invariant(
        typeof data === "string",
        `Expected string data for mime=${mimetype}. Got ${typeof data}`,
      );
      return <ImageOutput className={channel} src={data} alt="" />;
    case "image/svg+xml":
      invariant(
        typeof data === "string",
        `Expected string data for mime=${mimetype}. Got ${typeof data}`,
      );
      return renderHTML({ html: data });

    case "video/mp4":
    case "video/mpeg":
      invariant(
        typeof data === "string",
        `Expected string data for mime=${mimetype}. Got ${typeof data}`,
      );
      return <VideoOutput className={channel} src={data} />;

    case "application/vnd.marimo+error":
      invariant(Array.isArray(data), "Expected array data");
      return <MarimoErrorOutput cellId={cellId} errors={data} />;

    case "application/vnd.marimo+traceback":
      invariant(
        typeof data === "string",
        `Expected string data for mime=${mimetype}. Got ${typeof data}`,
      );
      return (
        <MarimoTracebackOutput
          onRefactorWithAI={onRefactorWithAI}
          traceback={data}
        />
      );

    case "text/csv":
      invariant(
        typeof data === "string",
        `Expected string data for mime=${mimetype}. Got ${typeof data}`,
      );
      return <CsvViewer contents={data} />;
    case "text/latex":
    case "text/markdown":
      invariant(
        typeof data === "string",
        `Expected string data for mime=${mimetype}. Got ${typeof data}`,
      );
      return (
        <LazyAnyLanguageCodeMirror
          theme={theme === "dark" ? "dark" : "light"}
          value={data}
          readOnly={true}
          editable={false}
          language="markdown"
        />
      );
    case "application/vnd.vegalite.v5+json":
    case "application/vnd.vega.v5+json":
      return (
        <LazyVegaLite
          spec={parsedJsonData as TopLevelFacetedUnitSpec}
          theme={theme === "dark" ? "dark" : undefined}
        />
      );
    case "application/vnd.marimo+mimebundle":
      return (
        <MimeBundleOutputRenderer
          channel={channel}
          data={
            parsedJsonData as Record<OutputMessage["mimetype"], OutputMessage>
          }
        />
      );
    default:
      logNever(mimetype);
      return (
        <div className="text-destructive">Unsupported mimetype: {mimetype}</div>
      );
  }
});
OutputRenderer.displayName = "OutputRenderer";

/**
 * Renders a mimebundle output.
 */
const MimeBundleOutputRenderer: React.FC<{
  channel: OutputMessage["channel"];
  data: MimeBundleOrTuple;
  cellId?: CellId;
}> = memo(({ data, channel, cellId }) => {
  const mimebundle = Array.isArray(data) ? data[0] : data;

  // If there is none, return null
  const first = Objects.keys(mimebundle)[0];
  if (!first) {
    return null;
  }

  // If there is only one mime type, render it directly
  if (Object.keys(mimebundle).length === 1) {
    return (
      <OutputRenderer
        cellId={cellId}
        message={{
          channel: channel,
          data: mimebundle[first],
          mimetype: first,
        }}
      />
    );
  }

  const mimeEntries = Objects.entries(mimebundle);
  // Sort HTML first
  mimeEntries.sort(([mimeA], [mimeB]) => {
    if (mimeA === "text/html") {
      return -1;
    }
    return 0;
  });

  return (
    <Tabs defaultValue={first} orientation="vertical">
      <div className="flex">
        <TabsList className="self-start max-h-none flex flex-col gap-2 mr-4 flex-shrink-0">
          {mimeEntries.map(([mime]) => (
            <TabsTrigger
              key={mime}
              value={mime}
              className="flex items-center space-x-2"
            >
              <Tooltip delayDuration={200} content={mime} side="right">
                <span>{renderMimeIcon(mime)}</span>
              </Tooltip>
            </TabsTrigger>
          ))}
        </TabsList>
        <div className="flex-1">
          {mimeEntries.map(([mime, output]) => (
            <TabsContent key={mime} value={mime}>
              <ErrorBoundary>
                <OutputRenderer
                  cellId={cellId}
                  message={{
                    channel: channel,
                    data: output,
                    mimetype: mime,
                  }}
                />
              </ErrorBoundary>
            </TabsContent>
          ))}
        </div>
      </div>
    </Tabs>
  );
});
MimeBundleOutputRenderer.displayName = "MimeBundleOutputRenderer";

interface OutputAreaProps {
  output: OutputMessage | null;
  cellId: CellId;
  stale: boolean;
  loading: boolean;
  /**
   * Whether to allow expanding the output
   * This shows the expand button and allows the user to expand the output
   */
  allowExpand: boolean;
  /**
   * Whether to force expand the output
   * When true, there will be no expand button and the output will be expanded.
   */
  forceExpand?: boolean;
  className?: string;
}

export const OutputArea = React.memo(
  ({
    output,
    cellId,
    stale,
    loading,
    allowExpand,
    forceExpand,
    className,
  }: OutputAreaProps) => {
    if (output === null) {
      return null;
    }
    if (output.channel === "output" && output.data === "") {
      return null;
    }

    // TODO(akshayka): More descriptive title
    // 1. This output is stale (this cell has been edited but not run)
    // 2. This output is stale (this cell is queued to run)
    // 3. This output is stale (its inputs have changed)
    const title = stale ? "This output is stale" : undefined;
    const Container = allowExpand ? ExpandableOutput : Div;

    return (
      <ErrorBoundary>
        <Container
          title={title}
          cellId={cellId}
          forceExpand={forceExpand}
          id={CellOutputId.create(cellId)}
          className={cn(
            stale && "marimo-output-stale",
            loading && "marimo-output-loading",
            className,
          )}
        >
          <OutputRenderer cellId={cellId} message={output} />
        </Container>
      </ErrorBoundary>
    );
  },
);
OutputArea.displayName = "OutputArea";

const Div = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<"div">
>((props, ref) => <div ref={ref} {...props} />);
Div.displayName = "Div";

/**
 * Detects if there is overflow in the output area and adds a button to optionally expand
 */
const ExpandableOutput = React.memo(
  ({
    cellId,
    children,
    forceExpand,
    ...props
  }: React.HTMLProps<HTMLDivElement> & {
    cellId: CellId;
    forceExpand?: boolean;
  }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const [isExpanded, setIsExpanded] = useExpandedOutput(cellId);
    const [isOverflowing, setIsOverflowing] = useState(false);

    // Create resize observer to detect overflow
    useEffect(() => {
      if (!containerRef.current) {
        return;
      }
      const el = containerRef.current;

      const detectOverflow = () => {
        setIsOverflowing(el.scrollHeight > el.clientHeight);
      };

      const resizeObserver = new ResizeObserver(detectOverflow);
      resizeObserver.observe(el);

      return () => {
        resizeObserver.disconnect();
      };
    }, [props.id]);

    return (
      <>
        <div>
          <div className="relative print:hidden">
            <div className="absolute -right-9 top-1 z-[1] flex flex-col gap-1">
              <Tooltip content="Fullscreen" side="left">
                <Button
                  data-testid="fullscreen-output-button"
                  className="hover-action hover:bg-muted p-1 hover:border-border border border-transparent"
                  onClick={async () => {
                    await containerRef.current?.requestFullscreen();
                  }}
                  onMouseDown={Events.preventFocus}
                  size="xs"
                  variant="text"
                >
                  <ExpandIcon className="size-4" strokeWidth={1.25} />
                </Button>
              </Tooltip>
              {(isOverflowing || isExpanded) && !forceExpand && (
                <Button
                  data-testid="expand-output-button"
                  className={cn(
                    "hover:border-border border border-transparent hover:bg-muted",
                    // Force show button if expanded
                    !isExpanded && "hover-action",
                  )}
                  onClick={() => setIsExpanded(!isExpanded)}
                  size="xs"
                  variant="text"
                >
                  {isExpanded ? (
                    <Tooltip content="Collapse output" side="left">
                      <ChevronsDownUpIcon className="h-4 w-4" />
                    </Tooltip>
                  ) : (
                    <Tooltip content="Expand output" side="left">
                      <ChevronsUpDownIcon className="h-4 w-4" />
                    </Tooltip>
                  )}
                </Button>
              )}
            </div>
          </div>
          <div
            {...props}
            data-cell-role="output"
            className={cn(
              "relative fullscreen:bg-background fullscreen:flex fullscreen:items-center fullscreen:justify-center",
              "fullscreen:[align-items:safe_center]",
              props.className,
            )}
            ref={containerRef}
            style={
              isExpanded || forceExpand ? { maxHeight: "none" } : undefined
            }
          >
            {children}
          </div>
        </div>
        <div className="increase-pointer-area-x contents print:hidden" />
      </>
    );
  },
);

ExpandableOutput.displayName = "ExpandableOutput";
