/* Copyright 2026 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */

import type { AnyWidget, Experimental } from "@anywidget/types";
import { asRemoteURL } from "@/core/runtime/config";
import { resolveVirtualFileURL } from "@/core/static/files";
import { isStaticNotebook } from "@/core/static/static-state";
import { Logger } from "@/utils/Logger";
import type { Model } from "./model";
import type { ModelState, WidgetModelId } from "./types";

export const experimental: Experimental = {
  invoke: async () => {
    const message =
      "anywidget.invoke not supported in marimo. Please file an issue at https://github.com/marimo-team/marimo/issues";
    Logger.warn(message);
    throw new Error(message);
  },
};

export type RenderFn = (el: HTMLElement, signal: AbortSignal) => Promise<void>;

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
    let url = asRemoteURL(jsUrl).toString();
    if (isStaticNotebook()) {
      url = resolveVirtualFileURL(url);
    }
    return import(/* @vite-ignore */ url);
  }
}

/**
 * Connects a Model to a resolved AnyWidget definition.
 * Owns the initialize lifecycle and produces a render function.
 *
 * Per AFM spec:
 * - initialize() is called once per model (or once per hot-reload)
 * - render() (the returned function) is called once per view
 */
class WidgetBinding<T extends ModelState = ModelState> {
  #controller: AbortController | undefined;
  #widgetDef: AnyWidget<T> | undefined;
  #render: RenderFn | undefined;

  /**
   * Bind a widget definition to a model.
   * If the same def is already bound, returns the cached render function.
   * If a different def is provided (hot reload), tears down the old binding
   * and re-initializes.
   */
  async bind(widgetDef: AnyWidget<T>, model: Model<T>): Promise<RenderFn> {
    // Already initialized with the same widget - return cached render
    if (this.#render && this.#widgetDef === widgetDef) {
      return this.#render;
    }

    // If widgetDef changed (hot reload), destroy old and re-initialize
    if (this.#render && this.#widgetDef !== widgetDef) {
      Logger.debug(
        "[WidgetBinding] Hot-reload detected, aborting previous binding",
      );
      this.#controller?.abort();
      this.#controller = undefined;
      this.#render = undefined;
    }

    this.#widgetDef = widgetDef;
    this.#controller = new AbortController();
    const bindingSignal = this.#controller.signal;

    // Resolve the widget definition (call if it's a function)
    const widget =
      typeof widgetDef === "function" ? await widgetDef() : widgetDef;

    // Call initialize once per model
    const cleanup = await widget.initialize?.({ model, experimental });
    if (cleanup) {
      bindingSignal.addEventListener("abort", cleanup);
    }

    // Store and return the render closure
    this.#render = async (el: HTMLElement, viewSignal: AbortSignal) => {
      const renderCleanup = await widget.render?.({
        model,
        el,
        experimental,
      });
      if (renderCleanup) {
        // Cleanup when either the view unmounts or the binding is destroyed
        const combined = abortSignalAny([viewSignal, bindingSignal]);
        combined.addEventListener("abort", () => {
          const reason = viewSignal.aborted
            ? "view unmount"
            : "binding destroyed";
          Logger.debug(
            `[WidgetBinding] Render cleanup triggered (reason: ${reason})`,
          );
          renderCleanup();
        });
      }
    };

    return this.#render;
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
    this.#render = undefined;
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
