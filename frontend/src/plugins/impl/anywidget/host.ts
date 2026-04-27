/* Copyright 2026 Marimo. All rights reserved. */

import type { AnyModel } from "@anywidget/types";
import { MODEL_MANAGER } from "./model";
import { modelProxy } from "./model-proxy";
import type { WidgetModelId } from "./types";
import { BINDING_MANAGER } from "./widget-binding";
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

const READY_TIMEOUT_MS = 10_000;

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
      const model = await MODEL_MANAGER.get(modelId);
      // Wrap in a proxy so listeners the parent registers on the child's
      // model are auto-cleared when the parent's view tears down.
      // The generic T is structural — modelProxy returns the underlying
      // AnyModel shape regardless of T, which the caller narrows.
      return modelProxy(model, parentSignal) as unknown as AnyModel<T>;
    },
    async getWidget<T = unknown>(ref: string): Promise<ResolvedWidget<T>> {
      const modelId = parseWidgetRef(ref) as WidgetModelId;
      // Surface a clear error fast if the child's frontend model never
      // arrived (e.g. the parent serialized a ref to a widget that was
      // never displayed and whose comm was never opened).
      await MODEL_MANAGER.get(modelId);
      const binding = BINDING_MANAGER.getOrCreate(modelId);

      // `binding.ready` resolves once the child's `initialize` settles.
      // We add an outer timeout so a child that's registered but never
      // bound (e.g. its `_esm` never loaded) fails loudly instead of
      // hanging the parent's render.
      let timer: ReturnType<typeof setTimeout> | undefined;
      const exports = await new Promise<unknown>((resolve, reject) => {
        timer = setTimeout(
          () =>
            reject(
              new Error(
                `[anywidget] Timed out waiting for widget ${modelId} to initialize`,
              ),
            ),
          READY_TIMEOUT_MS,
        );
        binding.ready.then(resolve, reject);
      }).finally(() => clearTimeout(timer));

      return {
        exports: exports as T,
        async render({ el, signal }) {
          await binding.createView({ el }, { signal: signal ?? parentSignal });
        },
      };
    },
  };
}
