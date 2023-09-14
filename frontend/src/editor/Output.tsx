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
  const outputCls: string = message.channel;
  // TODO(akshayka): audio; pdf; text/csv; excel?; text/css; text/javascript
  switch (message.mimetype) {
    case "text/html":
      return <HtmlOutput className={outputCls} html={message.data} />;

    case "text/plain":
      return <TextOutput className={outputCls} text={message.data} />;

    case "application/json":
      // TODO: format is 'auto', but should make configurable once cells can
      // support config
      return (
        <JsonOutput className={outputCls} data={parsedJsonData} format="auto" />
      );
    case "image/png":
    case "image/svg+xml":
    case "image/tiff":
    case "image/avif":
    case "image/bmp":
    case "image/gif":
    case "image/jpeg":
      return <ImageOutput className={outputCls} src={message.data} alt="" />;

    case "video/mp4":
    case "video/mpeg":
      return <VideoOutput className={outputCls} src={message.data} />;

    case "application/vnd.marimo+error":
      return <MarimoErrorOutput errors={message.data} />;

    default:
      logNever(message);
      return null;
  }
}

export const OutputArea = React.memo(
  (props: { output: OutputMessage | null; cellId: CellId; stale: boolean }) => {
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
      const title = props.stale ? "This output is stale" : undefined;
      return (
        <div
          title={title}
          id={`output-${props.cellId}`}
          className={cn("OutputArea", props.stale && "marimo-output-stale")}
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

export const ConsoleOutputArea = (props: {
  consoleOutputs: OutputMessage[];
  cellId: CellId;
  stale: boolean;
}): React.ReactNode => {
  if (props.consoleOutputs.length === 0) {
    return null;
  }

  const cls = `ConsoleOutputArea${props.stale ? " marimo-output-stale" : ""}`;
  const title = props.stale ? "This console output is stale" : undefined;
  return (
    <div title={title} className={cls}>
      {props.consoleOutputs.map((output) =>
        formatOutput({
          message: output,
        })
      )}
    </div>
  );
};
