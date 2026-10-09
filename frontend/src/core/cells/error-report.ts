/* Copyright 2026 Marimo. All rights reserved. */

import { describeError } from "@/core/errors/error-entries";
import type { MarimoError } from "@/core/kernel/messages";
import { sanitizeHtml } from "@/plugins/core/sanitize-html";
import { parseHtmlContent } from "@/utils/dom";
import type { CellId } from "./ids";

export interface CellOutputHandoff<Output> {
  type: "cell-output";
  cell_id: CellId;
  code?: string;
  output: Output;
}

export interface ErrorHandoffOutput {
  type: "error";
  message: string;
  traceback?: string;
}

export function buildErrorReport(
  cellId: CellId,
  evidence: { code?: string } & (
    | { errors: MarimoError[] }
    | { traceback: string }
  ),
): CellOutputHandoff<ErrorHandoffOutput> {
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
    traceback = parseHtmlContent(sanitizeHtml(evidence.traceback));
    message = traceback.split("\n").findLast((line) => line.length > 0) ?? "";
  }

  return {
    type: "cell-output",
    cell_id: cellId,
    ...(evidence.code === undefined ? {} : { code: evidence.code }),
    output: {
      type: "error",
      message,
      ...(traceback ? { traceback } : {}),
    },
  };
}
