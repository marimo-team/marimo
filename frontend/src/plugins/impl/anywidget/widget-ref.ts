/* Copyright 2026 Marimo. All rights reserved. */

import { isWidgetModelId, type WidgetModelId } from "./types";

export const WIDGET_REF_PREFIX = "anywidget:";

/**
 * Parse a widget reference string into its model id.
 *
 * Per anywidget>=0.11, widget refs are serialized as
 * `anywidget:<model_id>` strings embedded directly in widget state.
 * `host.getWidget(ref)` consumes these strings.
 *
 * The legacy `IPY_MODEL_<id>` prefix used by ipywidgets'
 * `widget_serialization` is intentionally NOT accepted here — widgets
 * using that path resolve children manually via
 * `model.widget_manager.get_model(id)` after stripping the prefix.
 */
export function parseWidgetRef(ref: unknown): WidgetModelId {
  if (typeof ref === "string" && ref.startsWith(WIDGET_REF_PREFIX)) {
    const modelId = ref.slice(WIDGET_REF_PREFIX.length);
    if (isWidgetModelId(modelId)) {
      return modelId;
    }
  }
  throw new Error(
    `[anywidget] Invalid widget reference: ${JSON.stringify(ref)}`,
  );
}
