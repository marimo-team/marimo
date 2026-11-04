/* Copyright 2026 Marimo. All rights reserved. */

import type { NotebookClient } from "@marimo-team/client";
import type { FunctionCallResultMessage } from "../kernel/messages";
import type { InvokeFunctionRequest } from "../network/types";

export type FunctionRequest = (
  request: Omit<InvokeFunctionRequest, "functionCallId">,
) => Promise<
  Pick<FunctionCallResultMessage, "status" | "return_value" | "found">
>;

/** Bind calls to the host and lifetime that supplied an element. */
export function createHostFunctionRequest(
  notebook: Pick<NotebookClient, "sendUIElement">,
  signal: AbortSignal,
): FunctionRequest {
  return async ({ namespace, functionName, args }) => {
    signal.throwIfAborted();
    const reply = await notebook.sendUIElement(
      namespace,
      { function: functionName, args },
      { signal },
    );
    // A completed HTTP request can race with a rerun or a backend switch.
    signal.throwIfAborted();
    if (!reply.ok) {
      throw new Error(reply.problem.detail ?? reply.problem.title);
    }
    return reply.data.result;
  };
}
