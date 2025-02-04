/* Copyright 2024 Marimo. All rights reserved. */
import { DeferredRequestRegistry } from "./DeferredRequestRegistry";
import type { MCPServerEvaluationRequest } from "./types";
import type { MCPServerEvaluationResult } from "../kernel/messages";
import { sendMCPEvaluationRequest } from "./requests";

export const MCP_REQUEST_REGISTRY = new DeferredRequestRegistry<
    Omit<MCPServerEvaluationRequest, "mcpEvaluationId">, 
    MCPServerEvaluationResult
>("mcp-evaluation-result", async (requestId, req) => { 
    await sendMCPEvaluationRequest({
        mcpEvaluationId: requestId,
        ...req,
    });
});
