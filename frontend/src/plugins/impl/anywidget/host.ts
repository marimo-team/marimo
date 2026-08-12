/* Copyright 2026 Marimo. All rights reserved. */

import type { AnyModel, Host, ResolvedWidget } from "@anywidget/types";
import { modelProxy } from "./model-proxy";
import type { Model } from "./model";
import type { ModelState } from "./types";
import type { WidgetModelId } from "./types";
import { parseWidgetRef } from "./widget-ref";

export type { Host, ResolvedWidget };

export interface WidgetResolver {
  getModel(key: WidgetModelId): Promise<Model<ModelState>>;
  getWidget<T = unknown>(key: WidgetModelId): Promise<ResolvedWidget<T>>;
}

/**
 * Build a `Host` scoped to a parent view's lifetime.
 *
 * The supplied `parentSignal` is used as the default for child renders
 * that don't pass their own `signal` — so a child mounted via
 * `host.getWidget(ref).render({ el })` is automatically torn down when
 * the parent view tears down. Listeners that the child registers on its
 * own model via `model.on(...)` are scoped to the same signal through
 * `modelProxy`.
 */
export function createHost(
  resolver: WidgetResolver,
  parentSignal: AbortSignal,
): Host {
  return {
    async getModel<T extends Record<string, unknown> = Record<string, unknown>>(
      ref: string,
    ): Promise<AnyModel<T>> {
      const modelId = parseWidgetRef(ref);
      const model = await resolver.getModel(modelId);
      // Wrap in a proxy so listeners the parent registers on the child's
      // model are auto-cleared when the parent's view tears down.
      // The generic T is structural — modelProxy returns the underlying
      // AnyModel shape regardless of T, which the caller narrows.
      return modelProxy(model, parentSignal) as unknown as AnyModel<T>;
    },
    async getWidget<T = unknown>(ref: string): Promise<ResolvedWidget<T>> {
      const modelId = parseWidgetRef(ref);
      const widget = await resolver.getWidget<T>(modelId);
      return {
        exports: widget.exports,
        async render({ el, signal }) {
          await widget.render({ el, signal: signal ?? parentSignal });
        },
      };
    },
  };
}
