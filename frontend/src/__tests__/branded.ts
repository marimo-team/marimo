/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Test-only helpers for constructing branded ID types from plain strings.
 *
 * In production code, branded types flow from the API (via codegen) or
 * from designated creation points (e.g. CellId.create()). Tests need to
 * construct these from string literals, which requires a cast. These
 * helpers centralise that cast so test files don't scatter `as CellId`
 * everywhere.
 */

import type { CellId, UIElementId } from "@/core/cells/ids";
import type { RequestId } from "@/core/network/DeferredRequestRegistry";
import type { VariableName } from "@/core/variables/types";

export const cellId = (s: string) => s as CellId;
export const variableName = (s: string) => s as VariableName;
export const requestId = (s: string) => s as RequestId;
export const uiElementId = (s: string) => s as UIElementId;
