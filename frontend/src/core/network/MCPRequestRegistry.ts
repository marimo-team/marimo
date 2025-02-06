/* Copyright 2024 Marimo. All rights reserved. */
import { DeferredRequestRegistry } from "./DeferredRequestRegistry";
import type { MCPEvaluationRequest } from "./types";
import type { MCPEvaluationResult } from "../kernel/messages";
import { sendMCPEvaluationRequest } from "./requests";

export const MCP_REQUEST_REGISTRY = new DeferredRequestRegistry<
  Omit<MCPEvaluationRequest, "mcpEvaluationId">,
  MCPEvaluationResult
>("mcp-evaluation-result", async (requestId, req) => {
  await sendMCPEvaluationRequest({
    mcpEvaluationId: requestId,
    ...req,
  });
});
