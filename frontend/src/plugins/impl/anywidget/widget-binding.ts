/* Copyright 2026 Marimo. All rights reserved. */
/* oxlint-disable typescript/no-explicit-any */

import type {
  AnyWidget,
  Experimental,
  Initialize,
  Render,
} from "@anywidget/types";
import { asRemoteURL } from "@/core/runtime/config";
import { resolveVirtualFileURL } from "@/core/static/files";
import { isStaticNotebook } from "@/core/static/static-state";
import { isTrustedVirtualFileUrl } from "@/plugins/core/trusted-url";
import { Deferred } from "@/utils/Deferred";
import { Logger } from "@/utils/Logger";
import { type Host, createHost } from "./host";
import type { Model } from "./model";
import { modelProxy } from "./model-proxy";
import type { ModelState, WidgetModelId } from "./types";

export const experimental: Experimental = {
  invoke: async () => {
    const message =
      "anywidget.invoke not supported in marimo. Please file an issue at https://github.com/marimo-team/marimo/issues";
    Logger.warn(message);
    throw new Error(message);
  },
};

/**
 * Polyfill for AbortSignal.any. Returns a signal that aborts when any of the
 * input signals abort. This can be removed once the Node.js test environment
 * (jsdom) supports AbortSignal.any natively.
 */
function abortSignalAny(signals: AbortSignal[]): AbortSignal {
  if (typeof AbortSignal.any === "function") {
    return AbortSignal.any(signals);
  }
  const controller = new AbortController();
  for (const signal of signals) {
    if (signal.aborted) {
      controller.abort(signal.reason);
      return controller.signal;
    }
    signal.addEventListener("abort", () => controller.abort(signal.reason), {
      once: true,
    });
  }
  return controller.signal;
}

/**
 * Deduplicates ESM imports by jsHash.
 * A single import is shared across all widget instances using the same module.
 */
class WidgetDefRegistry {
  #cache = new Map<string, Promise<any>>();

  /**
   * Get (or start) the ESM import for a widget module.
   * Cached by jsHash so multiple instances share one import.
   */
  getModule(jsUrl: string, jsHash: string): Promise<any> {
    const cached = this.#cache.get(jsHash);
    if (cached) {
      return cached;
    }

    const promise = this.#doImport(jsUrl).catch((error) => {
      // On failure, remove from cache so a retry with a new URL can work
      this.#cache.delete(jsHash);
      throw error;
    });

    this.#cache.set(jsHash, promise);
    return promise;
  }

  /**
   * Invalidate a cached module (e.g. for hot-reload support).
   */
  invalidate(jsHash: string): void {
    Logger.debug(
      `[WidgetDefRegistry] Invalidating module cache for hash=${jsHash}`,
    );
    this.#cache.delete(jsHash);
  }

  async #doImport(jsUrl: string): Promise<any> {
    // Only trust marimo virtual file paths. Accepting arbitrary URLs
    // would let a raw `<marimo-anywidget data-js-url=...>` element
    // embedded in a markdown cell dynamically import attacker-controlled
    // JavaScript at same origin (the HTML sanitizer allows any marimo-*
    // custom element with any attribute through to the plugin layer).
    if (!isTrustedVirtualFileUrl(jsUrl)) {
      throw new Error(
        `Refusing to load anywidget module from untrusted URL: ${String(
          jsUrl,
        )}`,
      );
    }
    let url = asRemoteURL(jsUrl).toString();
    if (isStaticNotebook()) {
      url = resolveVirtualFileURL(url);
    }
    return import(/* @vite-ignore */ url);
  }
}

/**
 * Resolved widget def — what `initialize` and `render` are actually called
 * on. `AnyWidget` is either this shape directly or a factory that returns it.
 */
interface ResolvedWidget<T extends ModelState> {
  initialize?: Initialize<T>;
  render?: Render<T>;
}

/**
 * Connects a Model to a resolved AnyWidget definition. Owns the
 * `initialize` lifecycle and exposes `createView` for mounting one or
 * more views. A binding may produce many views over its lifetime —
 * either from the cell's main React mount, or (per anywidget>=0.11)
 * from a parent's `host.getWidget(ref).render(...)` call.
 *
 * Per AFM spec:
 * - initialize() is called once per model (or once per hot-reload)
 * - render() is called once per view (zero or more per binding)
 */
class WidgetBinding<T extends ModelState = ModelState> {
  #controller: AbortController | undefined;
  #widgetDef: AnyWidget<T> | undefined;
  #widget: ResolvedWidget<T> | undefined;
  #model: Model<T> | undefined;
  #exports: unknown;
  #ready: Deferred<unknown>;

  /**
   * Resolves with the value returned from `initialize` once it has settled.
   * If `initialize` returns a cleanup function (legacy) or `void`, this
   * resolves with `undefined`. If it returns an object (anywidget>=0.11
   * exports), this resolves with that object.
   *
   * On hot-reload re-bind, the previous `ready` is rejected so any awaiters
   * (e.g. a parent's `host.getWidget()`) unblock instead of holding a stale
   * snapshot.
   */
  get ready(): Promise<unknown> {
    return this.#ready.promise;
  }

  /**
   * The object returned from `initialize`, or `undefined` if `initialize`
   * returned a cleanup function or nothing. Synchronous mirror of `ready`.
   */
  get exports(): unknown {
    return this.#exports;
  }

  constructor() {
    this.#ready = new Deferred<unknown>();
    // Pre-attach a no-op catch so a re-bind rejection of an unawaited
    // `ready` doesn't surface as an unhandled rejection.
    this.#ready.promise.catch(() => undefined);
  }

  /**
   * Bind a widget definition to a model. Idempotent for the same
   * `(widgetDef, model)` pair. On hot reload (different `widgetDef`), the
   * previous lifecycle is torn down and `initialize` re-runs.
   */
  async bind(widgetDef: AnyWidget<T>, model: Model<T>): Promise<void> {
    // Already initialized with the same widget — nothing to do.
    if (this.#widgetDef === widgetDef && this.#model === model) {
      return;
    }

    // If widgetDef changed (hot reload), abort the previous binding even if
    // its `initialize` is still in flight — checking `#widgetDef` (set at
    // the start of bind) catches the in-flight case.
    if (this.#widgetDef && this.#widgetDef !== widgetDef) {
      Logger.debug(
        "[WidgetBinding] Hot-reload detected, aborting previous binding",
      );
      this.#controller?.abort();
      this.#controller = undefined;
      this.#widget = undefined;
      this.#exports = undefined;
      // Reject the old ready so any parent awaiting it unblocks instead of
      // resolving with stale exports from the previous module.
      this.#ready.reject(
        new Error("[anywidget] widget bind aborted by re-bind"),
      );
      this.#ready = new Deferred<unknown>();
      this.#ready.promise.catch(() => undefined);
    }

    this.#widgetDef = widgetDef;
    this.#model = model;
    this.#controller = new AbortController();
    const bindingSignal = this.#controller.signal;

    // Resolve the widget definition (call if it's a factory function).
    const widget = (
      typeof widgetDef === "function" ? await widgetDef() : widgetDef
    ) as ResolvedWidget<T>;

    // Call initialize once per model. `signal` aborts when the binding is
    // destroyed (cell re-run, hot-reload, model destroyed). Listeners
    // registered via `model.on(...)` inside `initialize` are auto-cleared
    // when `bindingSignal` fires (via `modelProxy`).
    const result = await widget.initialize?.({
      model: modelProxy(model, bindingSignal),
      experimental,
      signal: bindingSignal,
    } as Parameters<NonNullable<typeof widget.initialize>>[0]);

    // If the binding was destroyed or re-bound mid-initialize, run any
    // cleanup callback and bail out without populating exports or
    // resolving the (now stale) deferred.
    if (bindingSignal.aborted) {
      if (typeof result === "function") {
        try {
          await result();
        } catch (error) {
          Logger.warn("[WidgetBinding] cleanup after abort threw", error);
        }
      }
      return;
    }

    // Distinguish anywidget's three return shapes:
    //   function → legacy cleanup callback (existing behavior)
    //   object   → widget exports (anywidget>=0.11)
    //   void     → nothing
    if (typeof result === "function") {
      bindingSignal.addEventListener("abort", result);
      this.#exports = undefined;
    } else if (typeof result === "object" && result !== null) {
      this.#exports = result;
    } else {
      this.#exports = undefined;
    }

    this.#widget = widget;
    this.#ready.resolve(this.#exports);
  }

  /**
   * Mount a view of this widget into `el`. Safe to call many times —
   * each view has its own combined signal that aborts when either the
   * caller's `signal` fires or the binding is destroyed. Listeners
   * registered via `model.on(...)` inside `render` are auto-cleared on
   * abort (via `modelProxy`).
   *
   * Awaits `ready` first so callers can call `createView` before
   * `bind` has finished `initialize`. If the binding has been destroyed
   * or re-bound, the awaited `ready` rejects and `createView` throws.
   */
  async createView(
    target: { el: HTMLElement },
    options: { signal: AbortSignal; host?: Host },
  ): Promise<void> {
    await this.#ready.promise;
    const widget = this.#widget;
    const model = this.#model;
    const bindingSignal = this.#controller?.signal;
    if (!widget?.render || !model || !bindingSignal) {
      return;
    }
    // `renderSignal` aborts when either the caller's view unmounts or
    // the binding itself is destroyed.
    const renderSignal = abortSignalAny([options.signal, bindingSignal]);
    if (renderSignal.aborted) {
      return;
    }
    // Each view gets its own `host` scoped to that view's signal — so a
    // child mounted via `host.getWidget(ref).render({ el })` cascades
    // teardown when this view tears down, not when the binding does.
    // Callers (e.g. `host.getWidget`) may pass through a host that's
    // already scoped to a parent's lifetime; honor that.
    const host = options.host ?? createHost(renderSignal);
    const renderCleanup = await widget.render({
      model: modelProxy(model, renderSignal),
      el: target.el,
      experimental,
      signal: renderSignal,
      host,
    } as Parameters<NonNullable<typeof widget.render>>[0]);
    if (renderCleanup) {
      renderSignal.addEventListener("abort", () => {
        const reason = options.signal.aborted
          ? "view unmount"
          : "binding destroyed";
        Logger.debug(
          `[WidgetBinding] Render cleanup triggered (reason: ${reason})`,
        );
        renderCleanup();
      });
    }
  }

  /**
   * Destroy this binding, aborting the initialize lifecycle.
   */
  destroy(): void {
    Logger.debug(
      "[WidgetBinding] Destroying binding, aborting initialize lifecycle",
    );
    this.#controller?.abort();
    this.#controller = undefined;
    this.#widgetDef = undefined;
    this.#widget = undefined;
    this.#model = undefined;
    this.#exports = undefined;
    // Unblock any pending awaiters of `ready` (e.g. a parent's
    // `host.getWidget()`).
    this.#ready.reject(new Error("[anywidget] binding destroyed"));
  }
}

/**
 * Maps WidgetModelId to WidgetBinding instances.
 * Singleton that manages the lifecycle of all bindings.
 */
class BindingManager {
  #bindings = new Map<WidgetModelId, WidgetBinding<any>>();

  getOrCreate(modelId: WidgetModelId): WidgetBinding<any> {
    let binding = this.#bindings.get(modelId);
    if (!binding) {
      binding = new WidgetBinding();
      this.#bindings.set(modelId, binding);
    }
    return binding;
  }

  destroy(modelId: WidgetModelId): void {
    const binding = this.#bindings.get(modelId);
    if (binding) {
      Logger.debug(`[BindingManager] Destroying binding for model=${modelId}`);
      binding.destroy();
      this.#bindings.delete(modelId);
    }
  }

  has(modelId: WidgetModelId): boolean {
    return this.#bindings.has(modelId);
  }
}

export const WIDGET_DEF_REGISTRY = new WidgetDefRegistry();
export const BINDING_MANAGER = new BindingManager();

export const visibleForTesting = {
  WidgetDefRegistry,
  WidgetBinding,
  BindingManager,
};
