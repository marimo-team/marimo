/* Copyright 2024 Marimo. All rights reserved. */
import React, { useEffect, useMemo, useRef, useState } from "react";

import { OutputMessage } from "@/core/kernel/messages";

import { logNever } from "../../utils/assertNever";
import { JsonOutput } from "./output/JsonOutput";
import { HtmlOutput } from "./output/HtmlOutput";
import { ImageOutput } from "./output/ImageOutput";
import { MarimoErrorOutput } from "./output/MarimoErrorOutput";
import { TextOutput } from "./output/TextOutput";
import { VideoOutput } from "./output/VideoOutput";
import { CellId } from "@/core/cells/ids";
import { cn } from "@/utils/cn";
import { ErrorBoundary } from "./boundary/ErrorBoundary";

import "./output/Outputs.css";
import { Button } from "../ui/button";
import { ChevronsDownUpIcon, ChevronsUpDownIcon } from "lucide-react";
import { Tooltip } from "../ui/tooltip";
import { useExpandedOutput } from "@/core/cells/outputs";

/**
 * Renders an output based on an OutputMessage.
 */
export function formatOutput({
  message,
  parsedJsonData = {},
}: {
  message: OutputMessage;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  parsedJsonData?: Record<string, any>;
}): React.ReactNode {
  const channel = message.channel;
  // TODO(akshayka): audio; pdf; text/csv; excel?; text/css; text/javascript
  switch (message.mimetype) {
    case "text/html":
      return <HtmlOutput className={channel} html={message.data} />;

    case "text/plain":
      return <TextOutput channel={channel} text={message.data} />;

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
      return <ImageOutput className={channel} src={message.data} alt="" />;

    case "video/mp4":
    case "video/mpeg":
      return <VideoOutput className={channel} src={message.data} />;

    case "application/vnd.marimo+error":
      return <MarimoErrorOutput errors={message.data} />;

    default:
      logNever(message);
      return null;
  }
}

interface OutputAreaProps {
  output: OutputMessage | null;
  cellId: CellId;
  stale: boolean;
  allowExpand: boolean;
  className?: string;
}

export const OutputArea = React.memo(
  ({ output, cellId, stale, allowExpand, className }: OutputAreaProps) => {
    // Memoize parsing the json data
    const parsedJsonData = useMemo(() => {
      if (!output) {
        return;
      }

      const { mimetype, data } = output;
      switch (mimetype) {
        case "application/json":
          return typeof data === "string" ? JSON.parse(data) : data;
        default:
          return;
      }
    }, [output]);

    if (output === null) {
      return null;
    } else if (output.channel === "output" && output.data === "") {
      return null;
    } else {
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
            {formatOutput({
              message: output,
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              parsedJsonData: parsedJsonData as Record<string, any>,
            })}
          </Container>
        </ErrorBoundary>
      );
    }
  }
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
          {(isOverflowing || isExpanded) && (
            <div className="relative">
              <Button
                className={cn(
                  "absolute top-6 -right-12 z-10",
                  // Force show button if expanded
                  !isExpanded && "hover-action"
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
            </div>
          )}
          <div
            {...props}
            className={cn("relative", props.className)}
            ref={containerRef}
            style={isExpanded ? { maxHeight: "none" } : undefined}
          >
            {children}
          </div>
        </div>
        <div className="increase-pointer-area-x contents" />
      </>
    );
  }
);

ExpandableOutput.displayName = "ExpandableOutput";
