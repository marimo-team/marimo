/* Copyright 2026 Marimo. All rights reserved. */

import type { AnyModel } from "@anywidget/types";
import type { ModelState } from "./types";

type ModelEventCallback = Parameters<AnyModel<ModelState>["on"]>[1];

/**
 * Wrap a model so every `on()` call from inside `initialize` or `render`
 * is auto-tied to a lifetime `AbortSignal`. When the signal aborts,
 * every listener registered through the proxy is removed.
 *
 * Without this, a parent widget that re-renders a child via
 * `host.getWidget().render` would accumulate listeners on the child's
 * model on every re-render — the widget author would have to know to
 * pass `signal` to each `on()` call themselves.
 *
 * The proxy is purely a host-side ergonomic helper. The widget author
 * still writes `model.on("change:foo", handler)` exactly as before; the
 * cleanup signal is supplied transparently.
 */
// oxlint-disable-next-line marimo/prefer-object-params -- concise internal helper used at protocol call sites
export function modelProxy<T extends ModelState>(
  model: AnyModel<T>,
  signal: AbortSignal,
): AnyModel<T> {
  return {
    get(key) {
      return model.get(key);
    },
    set(key, value) {
      model.set(key, value);
    },
    save_changes() {
      model.save_changes();
    },
    send: model.send.bind(model),
    on(name: string, callback: ModelEventCallback): void {
      if (signal.aborted) {
        return;
      }
      model.on(name, callback);
      signal.addEventListener("abort", () => model.off(name, callback), {
        once: true,
      });
    },
    off(name?: string | null, callback?: ModelEventCallback | null): void {
      model.off(name ?? null, callback ?? null);
    },
    widget_manager: {
      async get_model<TT extends ModelState>(modelId: string) {
        const child = await model.widget_manager.get_model<TT>(modelId);
        return modelProxy(child, signal);
      },
    },
  };
}
