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
import type { CellId } from "@/core/cells/ids";
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

/**
 * Renders an output based on an OutputMessage.
 */
export const OutputRenderer: React.FC<{
  message: OutputMessage;
  onRefactorWithAI?: (opts: { prompt: string }) => void;
}> = memo((props) => {
  const { message, onRefactorWithAI } = props;

  // Memoize parsing the json data
  const parsedJsonData = useMemo(() => {
    const data = message.data;
    switch (message.mimetype) {
      case "application/json":
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
    case "image/svg+xml":
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

    case "video/mp4":
    case "video/mpeg":
      invariant(
        typeof data === "string",
        `Expected string data for mime=${mimetype}. Got ${typeof data}`,
      );
      return <VideoOutput className={channel} src={data} />;

    case "application/vnd.marimo+error":
      invariant(Array.isArray(data), "Expected array data");
      return <MarimoErrorOutput errors={data} />;

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
    case "text/markdown":
      invariant(
        typeof data === "string",
        `Expected string data for mime=${mimetype}. Got ${typeof data}`,
      );
      return <LazyAnyLanguageCodeMirror value={data} language="markdown" />;
    default:
      logNever(mimetype);
      return null;
  }
});
OutputRenderer.displayName = "OutputRenderer";

interface OutputAreaProps {
  output: OutputMessage | null;
  cellId: CellId;
  stale: boolean;
  allowExpand: boolean;
  className?: string;
}

export const OutputArea = React.memo(
  ({ output, cellId, stale, allowExpand, className }: OutputAreaProps) => {
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
          id={`output-${cellId}`}
          className={cn(stale && "marimo-output-stale", className)}
        >
          <OutputRenderer message={output} />
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
    ...props
  }: React.HTMLProps<HTMLDivElement> & {
    cellId: CellId;
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
            <div className="absolute top-6 -right-11 z-10 flex flex-col gap-1">
              <Tooltip content="Fullscreen" side="left">
                <Button
                  data-testid="fullscreen-output-button"
                  className="hover-action hover:bg-muted"
                  onClick={async () => {
                    await containerRef.current?.requestFullscreen();
                  }}
                  size="xs"
                  variant="text"
                >
                  <ExpandIcon className="h-4 w-4" />
                </Button>
              </Tooltip>
              {(isOverflowing || isExpanded) && (
                <Button
                  data-testid="expand-output-button"
                  className={cn(
                    // Force show button if expanded
                    !isExpanded && "hover-action hover:bg-muted",
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
            className={cn(
              "relative fullscreen:bg-background fullscreen:flex fullscreen:items-center fullscreen:justify-center",
              props.className,
            )}
            ref={containerRef}
            style={isExpanded ? { maxHeight: "none" } : undefined}
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
