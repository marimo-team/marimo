/* Copyright 2023 Marimo. All rights reserved. */
import React, { useMemo } from "react";

import { OutputMessage } from "@/core/kernel/messages";

import { logNever } from "../utils/assertNever";
import { JsonOutput } from "./output/JsonOutput";
import { HtmlOutput } from "./output/HtmlOutput";
import { ImageOutput } from "./output/ImageOutput";
import { MarimoErrorOutput } from "./output/MarimoErrorOutput";
import { TextOutput } from "./output/TextOutput";
import { VideoOutput } from "./output/VideoOutput";
import { CellId } from "@/core/model/ids";
import { cn } from "@/lib/utils";

import "./output/Outputs.css";

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

export const OutputArea = React.memo(
  (props: {
    output: OutputMessage | null;
    cellId: CellId;
    stale: boolean;
    className?: string;
  }) => {
    // Memoize parsing the json data
    const parsedJsonData = useMemo(() => {
      if (!props.output) {
        return;
      }

      const { mimetype, data } = props.output;
      switch (mimetype) {
        case "application/json":
          return typeof data === "string" ? JSON.parse(data) : data;
        default:
          return;
      }
    }, [props.output]);

    if (props.output === null) {
      return null;
    } else if (props.output.channel === "output" && props.output.data === "") {
      return null;
    } else {
      // TODO(akshayka): More descriptive title
      // 1. This output is stale (this cell has been edited but not run)
      // 2. This output is stale (this cell is queued to run)
      // 3. This output is stale (its inputs have changed)
      const title = props.stale ? "This output is stale" : undefined;
      return (
        <div
          title={title}
          id={`output-${props.cellId}`}
          className={cn(props.stale && "marimo-output-stale", props.className)}
        >
          {formatOutput({
            message: props.output,
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            parsedJsonData: parsedJsonData as Record<string, any>,
          })}
        </div>
      );
    }
  }
);
OutputArea.displayName = "OutputArea";
