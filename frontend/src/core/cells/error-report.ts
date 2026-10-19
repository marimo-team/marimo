/* Copyright 2026 Marimo. All rights reserved. */

import { describeError } from "@/core/errors/error-entries";
import type { MarimoError } from "@/core/kernel/messages";
import { sanitizeHtml } from "@/plugins/core/sanitize-html";
import { parseHtmlContent } from "@/utils/dom";
import type { CellId } from "./ids";

export interface CellOutputMessage<Output> {
  type: "cell-output";
  cell_id: CellId;
  code?: string;
  output: Output;
}

export interface ErrorMessageOutput {
  type: "error";
  instructions: string;
  message: string;
  traceback?: string;
}

export const ERROR_MESSAGE_INSTRUCTIONS = "Fix this notebook error.";

export function buildErrorReport(
  cellId: CellId,
  evidence: { code?: string } & (
    | { errors: MarimoError[] }
    | { traceback: string; tracebackFormat: "html" | "text" }
  ),
): CellOutputMessage<ErrorMessageOutput> {
  let message: string;
  let traceback: string;
  if ("errors" in evidence) {
    message = evidence.errors.map(describeError).join("\n");
    traceback = evidence.errors
      .flatMap((error) =>
        "traceback" in error && error.traceback
          ? [parseHtmlContent(sanitizeHtml(error.traceback))]
          : [],
      )
      .join("\n\n");
  } else {
    traceback =
      evidence.tracebackFormat === "html"
        ? parseHtmlContent(sanitizeHtml(evidence.traceback))
        : evidence.traceback;
    message = traceback.split("\n").findLast((line) => line.length > 0) ?? "";
  }

  // Put repair intent before evidence so it survives prefix truncation.
  return {
    type: "cell-output",
    cell_id: cellId,
    output: {
      type: "error",
      instructions: ERROR_MESSAGE_INSTRUCTIONS,
      message,
      ...(traceback ? { traceback } : {}),
    },
    ...(evidence.code === undefined ? {} : { code: evidence.code }),
  };
}
