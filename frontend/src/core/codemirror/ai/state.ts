/* Copyright 2026 Marimo. All rights reserved. */

import { singleFacet } from "../facet";

interface ContextCallbacks {
  addAttachment?: (attachment: File) => void;
}

/**
 * State for completion callbacks
 */
export const contextCallbacks = singleFacet<ContextCallbacks>();
