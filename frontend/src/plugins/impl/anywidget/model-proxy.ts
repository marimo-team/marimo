/* Copyright 2026 Marimo. All rights reserved. */

import type { AnyModel } from "@anywidget/types";
import type { Model } from "./model";
import type { ModelState } from "./types";

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
export function modelProxy<T extends ModelState>(
  model: Model<T>,
  signal: AbortSignal,
): AnyModel<T> {
  return {
    get: model.get.bind(model),
    set: model.set.bind(model),
    save_changes: model.save_changes.bind(model),
    // marimo's send returns Promise<void>; AnyModel declares void. The
    // returned promise is ignored at the AnyModel boundary, which is fine.
    send: model.send.bind(model) as AnyModel<T>["send"],
    on(name: string, callback: (...args: unknown[]) => void): void {
      model.on(name, callback, { signal });
    },
    off(
      name?: string | null,
      callback?: ((...args: unknown[]) => void) | null,
    ): void {
      model.off(name ?? null, callback ?? null);
    },
    widget_manager: model.widget_manager,
  } as AnyModel<T>;
}
