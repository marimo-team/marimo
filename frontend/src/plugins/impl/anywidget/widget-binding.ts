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
import { Logger } from "@/utils/Logger";
import { type Host, createHost } from "./host";
import type { Model } from "./model";
import { modelProxy, type ProxyRegistration } from "./model-proxy";
import type { ModelState } from "./types";

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
   * Get (or start) the ESM import for a widget module, cached by
   * jsHash so multiple instances share one import. Pass
   * `kernelAuthored: true` only for URLs from an `EsmSpec`; it widens
   * the import gate to remote and data URLs.
   */
  getModule(
    jsUrl: string,
    jsHash: string,
    opts: { kernelAuthored?: boolean } = {},
  ): Promise<any> {
    const cached = this.#cache.get(jsHash);
    if (cached) {
      return cached;
    }

    const promise = this.#doImport(jsUrl, opts).catch((error) => {
      // On failure, remove from cache so a retry with a new URL can work
      this.#cache.delete(jsHash);
      throw error;
    });

    this.#cache.set(jsHash, promise);
    return promise;
  }

  async #doImport(
    jsUrl: string,
    opts: { kernelAuthored?: boolean } = {},
  ): Promise<any> {
    // By default, only trust marimo virtual file paths: arbitrary URLs
    // would let markdown-injected elements import attacker-controlled
    // JavaScript. Kernel-authored URLs (from an `EsmSpec`) are exempt —
    // a client cannot forge a notification to its peers. data: URLs
    // cover runtimes where virtual files are unsupported.
    const trusted =
      isTrustedVirtualFileUrl(jsUrl) ||
      (opts.kernelAuthored === true && /^(https?:|data:)/.test(jsUrl));
    if (!trusted) {
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
 * One live view of a binding, tracked so a generation swap can
 * re-render into the same elements. `signal` is the caller's own
 * signal, because the replacement view must outlive this generation.
 */
export interface TrackedView {
  el: HTMLElement;
  signal: AbortSignal;
  host?: Host;
}

/**
 * One immutable generation of a widget: a resolved AnyWidget definition
 * paired with a Model. Constructed by `WidgetBinding.create` and never
 * rebinds; a code change replaces the whole generation.
 *
 * Per AFM spec:
 * - initialize() ran exactly once, in `create`
 * - render() runs once per view (zero or more per generation)
 */
export class WidgetBinding<T extends ModelState = ModelState> {
  #controller: AbortController;
  #widget: ResolvedWidget<T>;
  #model: Model<T>;
  #exports: unknown;
  #views = new Set<TrackedView>();

  private constructor(
    widget: ResolvedWidget<T>,
    model: Model<T>,
    exports: unknown,
    controller: AbortController,
  ) {
    this.#widget = widget;
    this.#model = model;
    this.#exports = exports;
    this.#controller = controller;
  }

  /**
   * Resolve the widget definition (calling it if it is a factory) and
   * run `initialize` exactly once, with its listeners scoped to
   * `controller`'s signal. Aborting the controller mid-initialize
   * still runs any legacy cleanup callback, and `create` rejects.
   */
  static async create<T extends ModelState>(
    widgetDef: AnyWidget<T>,
    model: Model<T>,
    controller: AbortController = new AbortController(),
  ): Promise<WidgetBinding<T>> {
    const signal = controller.signal;
    const widget = (
      typeof widgetDef === "function" ? await widgetDef() : widgetDef
    ) as ResolvedWidget<T>;

    const initPromise = Promise.resolve(
      widget.initialize?.({
        model: modelProxy(model, signal),
        experimental,
        signal,
      } as Parameters<NonNullable<typeof widget.initialize>>[0]),
    );
    // If destroyed mid-initialize, still run a late-arriving legacy
    // cleanup callback: the widget acquired resources.
    initPromise
      .then(async (settled) => {
        if (signal.aborted && typeof settled === "function") {
          await settled();
        }
      })
      .catch((error) => {
        if (signal.aborted) {
          Logger.warn("[WidgetBinding] cleanup after abort threw", error);
        }
      });

    // Race against destruction so a hung `initialize` can't strand
    // callers whose model already closed.
    const result = await Promise.race([
      initPromise,
      new Promise<never>((_, reject) => {
        const abort = () => reject(new Error("[anywidget] binding destroyed"));
        if (signal.aborted) {
          abort();
          return;
        }
        signal.addEventListener("abort", abort, { once: true });
      }),
    ]);

    if (signal.aborted) {
      throw new Error("[anywidget] binding destroyed");
    }

    // Distinguish anywidget's three return shapes:
    //   function → legacy cleanup callback (run on destroy)
    //   object   → widget exports (anywidget>=0.11)
    //   void     → nothing
    let exports: unknown;
    if (typeof result === "function") {
      signal.addEventListener("abort", result as () => void);
      exports = undefined;
    } else if (typeof result === "object" && result !== null) {
      exports = result;
    } else {
      exports = undefined;
    }

    return new WidgetBinding(widget, model, exports, controller);
  }

  /**
   * The object returned from `initialize`, or `undefined` if it
   * returned a cleanup function or nothing.
   */
  get exports(): unknown {
    return this.#exports;
  }

  /**
   * Views currently mounted from this binding.
   */
  get liveViews(): readonly TrackedView[] {
    return [...this.#views];
  }

  /**
   * Mount a view of this widget into `el`. Each view's signal aborts
   * when the caller's `signal` fires or the binding is destroyed, and
   * listeners registered inside `render` auto-clear on abort.
   *
   * Hydration guarantee: listeners attached during `render` observe
   * current model state exactly once, after `render` settles. Scoped
   * to this view's listeners; re-firing at other views double-paints.
   */
  async createView(
    target: { el: HTMLElement },
    options: { signal: AbortSignal; host?: Host },
  ): Promise<void> {
    const widget = this.#widget;
    if (!widget.render) {
      return;
    }
    // `renderSignal` aborts when either the caller's view unmounts or
    // the binding itself is destroyed.
    const renderSignal = abortSignalAny([
      options.signal,
      this.#controller.signal,
    ]);
    if (renderSignal.aborted) {
      return;
    }
    const view: TrackedView = {
      el: target.el,
      signal: options.signal,
      host: options.host,
    };
    this.#views.add(view);
    renderSignal.addEventListener("abort", () => this.#views.delete(view), {
      once: true,
    });
    // Clear whatever a previous generation or render left behind.
    target.el.innerHTML = "";
    // Each view gets a `host` scoped to its own signal so child views
    // tear down with this view; callers may pass a host already scoped
    // to a parent's lifetime.
    const host = options.host ?? createHost(renderSignal);
    const registrations: ProxyRegistration[] = [];
    const renderCleanup = await widget.render({
      model: modelProxy(this.#model, renderSignal, (registration) =>
        registrations.push(registration),
      ),
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
    this.#replayState(registrations, renderSignal);
  }

  /**
   * The hydration guarantee documented on `createView`.
   */
  #replayState(
    registrations: readonly ProxyRegistration[],
    renderSignal: AbortSignal,
  ): void {
    const changePrefix = "change:";
    for (const { event, callback } of registrations) {
      if (renderSignal.aborted) {
        return;
      }
      try {
        if (event.startsWith(changePrefix)) {
          const key = event.slice(changePrefix.length);
          callback(this.#model.get(key));
        } else if (event === "change") {
          callback();
        }
      } catch (error) {
        Logger.error("[WidgetBinding] Error replaying state", error);
      }
    }
  }

  /**
   * Destroy this generation, running initialize/render cleanups and
   * clearing listeners registered through its model proxies.
   */
  destroy(): void {
    Logger.debug("[WidgetBinding] Destroying binding generation");
    this.#controller.abort();
  }
}

export const WIDGET_DEF_REGISTRY = new WidgetDefRegistry();

export const visibleForTesting = {
  WidgetDefRegistry,
  WidgetBinding,
};
