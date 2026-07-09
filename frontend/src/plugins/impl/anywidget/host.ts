/* Copyright 2026 Marimo. All rights reserved. */

import type { AnyModel } from "@anywidget/types";
import { modelProxy } from "./model-proxy";
import { WIDGET_REGISTRY } from "./registry";
import type { WidgetModelId } from "./types";
import { parseWidgetRef } from "./widget-ref";

/**
 * The `host` prop passed to a widget's `render`. Lets a parent widget
 * resolve a child widget by reference, mirroring the anywidget>=0.11
 * `Host` interface.
 */
export interface Host {
  getWidget<T = unknown>(ref: string): Promise<ResolvedWidget<T>>;
  getModel<T extends Record<string, unknown> = Record<string, unknown>>(
    ref: string,
  ): Promise<AnyModel<T>>;
}

export interface ResolvedWidget<T = unknown> {
  exports: T;
  render(opts: { el: HTMLElement; signal?: AbortSignal }): Promise<void>;
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
export function createHost(parentSignal: AbortSignal): Host {
  return {
    async getModel<T extends Record<string, unknown> = Record<string, unknown>>(
      ref: string,
    ): Promise<AnyModel<T>> {
      const modelId = parseWidgetRef(ref) as WidgetModelId;
      const model = await WIDGET_REGISTRY.getModel(modelId);
      // Wrap in a proxy so listeners the parent registers on the child's
      // model are auto-cleared when the parent's view tears down.
      // The generic T is structural — modelProxy returns the underlying
      // AnyModel shape regardless of T, which the caller narrows.
      return modelProxy(model, parentSignal) as unknown as AnyModel<T>;
    },
    async getWidget<T = unknown>(ref: string): Promise<ResolvedWidget<T>> {
      const modelId = parseWidgetRef(ref) as WidgetModelId;
      // The registry binds from the ESM spec if nothing else has, so
      // this works for children never displayed on their own.
      const { binding } = await WIDGET_REGISTRY.getWidget(modelId);
      return {
        exports: binding.exports as T,
        async render({ el, signal }) {
          await binding.createView({ el }, { signal: signal ?? parentSignal });
        },
      };
    },
  };
}
