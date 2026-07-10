/* Copyright 2026 Marimo. All rights reserved. */
import { Deferred } from "@/utils/Deferred";
import { Logger } from "@/utils/Logger";
import type { Host, ResolvedWidget } from "@anywidget/types";
import type { Model } from "./model";
import {
  getInvalidAnyWidgetModuleError,
  resolveAnyWidget,
} from "./resolve-widget";
import type { EsmSpec, ModelState, WidgetModelId } from "./types";
import { WIDGET_DEF_REGISTRY, WidgetBinding } from "./widget-binding";

interface Generation {
  hash: string;
  controller: AbortController;
  promise: Promise<WidgetBinding<ModelState>>;
}

interface RuntimeView {
  el: HTMLElement;
  signal: AbortSignal;
  generation?: Generation;
}

interface StyleMount {
  references: number;
  update(css: string): void;
  dispose(): void;
}

interface WidgetRuntimeOptions {
  timeout: number;
  isEditMode: () => boolean;
  createHost: (signal: AbortSignal) => Host;
  onModelTimeout: () => void;
}

type StyleRoot = Document | ShadowRoot;

/**
 * The complete browser-side lifetime of one widget model.
 *
 * A runtime survives ESM generation changes. It owns initialization,
 * mounted views, composition hosts, styles, and teardown so callers never
 * need to coordinate those concerns themselves.
 */
export class WidgetRuntime {
  readonly #key: WidgetModelId;
  readonly #timeout: number;
  readonly #isEditMode: () => boolean;
  readonly #createHost: (signal: AbortSignal) => Host;
  readonly #onModelTimeout: () => void;
  readonly #controller = new AbortController();
  readonly #model = new Deferred<Model<ModelState>>();
  readonly #views = new Set<RuntimeView>();
  readonly #styleMounts = new Map<StyleRoot, StyleMount>();
  #modelTimeout: ReturnType<typeof setTimeout> | undefined;
  #esmSpec: EsmSpec | undefined;
  #generation: Generation | undefined;
  #generationCleanup = Promise.resolve();
  #css = "";

  constructor(key: WidgetModelId, options: WidgetRuntimeOptions) {
    this.#key = key;
    this.#timeout = options.timeout;
    this.#isEditMode = options.isEditMode;
    this.#createHost = options.createHost;
    this.#onModelTimeout = options.onModelTimeout;
  }

  getModel(): Promise<Model<ModelState>> {
    if (this.#model.status === "pending" && !this.#modelTimeout) {
      this.#modelTimeout = setTimeout(() => {
        if (this.#model.status === "pending") {
          this.#modelTimeout = undefined;
          this.#model.reject(
            new Error(`Model not found for key: ${this.#key}`),
          );
          this.#onModelTimeout();
        }
      }, this.#timeout);
    }
    return this.#model.promise;
  }

  getModelSync(): Model<ModelState> | undefined {
    return this.#model.status === "resolved" ? this.#model.value : undefined;
  }

  createModel(factory: (signal: AbortSignal) => Model<ModelState>): void {
    if (this.#model.status !== "pending") {
      return;
    }
    this.#resolveModel(factory(this.#controller.signal));
  }

  setModel(model: Model<ModelState>): void {
    if (this.#model.status !== "pending") {
      return;
    }
    this.#resolveModel(model);
  }

  #resolveModel(model: Model<ModelState>): void {
    if (this.#modelTimeout) {
      clearTimeout(this.#modelTimeout);
      this.#modelTimeout = undefined;
    }
    this.#model.resolve(model);
    const css = model.get("_css");
    this.#css = typeof css === "string" ? css : "";
    model.on(
      "change:_css",
      (value: unknown) => {
        this.#css = typeof value === "string" ? value : "";
        for (const mount of this.#styleMounts.values()) {
          mount.update(this.#css);
        }
      },
      { signal: this.#controller.signal },
    );
  }

  setSpec(spec: EsmSpec): void {
    if (!this.#esmSpec) {
      this.#esmSpec = spec;
      return;
    }
    // A viewer's code is immutable for the lifetime of its model. This
    // also covers a viewer that receives an editor's update before its
    // first view creates a generation.
    if (!this.#isEditMode()) {
      return;
    }
    this.#esmSpec = spec;
    if (this.#generation && this.#generation.hash !== spec.hash) {
      this.#swapGeneration(spec);
    }
  }

  async getWidget<T = unknown>(): Promise<ResolvedWidget<T>> {
    const binding = await this.#getCurrentBinding();
    return {
      exports: binding.exports as T,
      render: async ({ el, signal }) => {
        await this.createView({
          el,
          signal: signal ?? this.#controller.signal,
        });
      },
    };
  }

  async createView(options: {
    el: HTMLElement;
    signal: AbortSignal;
  }): Promise<void> {
    if (options.signal.aborted || this.#controller.signal.aborted) {
      return;
    }
    const view: RuntimeView = {
      el: options.el,
      signal: options.signal,
    };
    this.#views.add(view);
    this.#mountStyle(view);
    options.signal.addEventListener("abort", () => this.#views.delete(view), {
      once: true,
    });
    await this.#renderView(view);
  }

  async #getCurrentBinding(): Promise<WidgetBinding<ModelState>> {
    while (!this.#controller.signal.aborted) {
      const model = await this.getModel();
      let generation = this.#generation;
      if (!generation) {
        const spec = this.#esmSpec;
        if (!spec) {
          throw new Error(
            `[anywidget] No ESM spec for model ${this.#key}: ` +
              "nothing ever provided this widget's code",
          );
        }
        generation = this.#startGeneration(spec, model);
      }
      try {
        const binding = await generation.promise;
        if (generation === this.#generation) {
          return binding;
        }
      } catch (error) {
        if (!this.#generation || generation === this.#generation) {
          throw error;
        }
      }
    }
    throw new Error("[anywidget] widget runtime destroyed");
  }

  async #createBinding(options: {
    spec: EsmSpec;
    model: Model<ModelState>;
    controller: AbortController;
  }): Promise<WidgetBinding<ModelState>> {
    const { spec, model, controller } = options;
    const mod = await WIDGET_DEF_REGISTRY.getModule({
      jsUrl: spec.url,
      jsHash: spec.hash,
      kernelAuthored: true,
    });
    const widget = resolveAnyWidget(mod, spec.url);
    if (!widget) {
      throw getInvalidAnyWidgetModuleError(mod, spec.url);
    }
    return WidgetBinding.create({
      widgetDef: widget,
      model,
      createHost: this.#createHost,
      controller,
    });
  }

  #startGeneration(spec: EsmSpec, model: Model<ModelState>): Generation {
    const controller = new AbortController();
    const generation: Generation = {
      hash: spec.hash,
      controller,
      promise: this.#createBinding({ spec, model, controller }),
    };
    generation.promise.catch(() => {
      if (this.#generation === generation) {
        this.#generation = undefined;
      }
    });
    this.#generation = generation;
    return generation;
  }

  #swapGeneration(spec: EsmSpec): void {
    const previous = this.#generation;
    if (!previous) {
      return;
    }
    Logger.debug(
      `[WidgetRuntime] Hot-swapping generation for model=${this.#key}`,
    );
    const cleanup = this.#queueGenerationCleanup(previous);
    const model = this.getModelSync();
    if (!model) {
      return;
    }
    const generation = this.#startGeneration(spec, model);
    for (const view of this.#views) {
      view.generation = undefined;
      void cleanup
        .then(() => this.#renderView(view, generation))
        .catch((error) => {
          Logger.error("[WidgetRuntime] Error replacing widget view", error);
        });
    }
  }

  #queueGenerationCleanup(generation: Generation): Promise<void> {
    // Abort immediately so pending initialize/render hooks see cancellation,
    // but serialize their settled cleanup before replacement DOM is rendered.
    generation.controller.abort();
    const cleanup = this.#generationCleanup.then(async () => {
      try {
        const binding = await generation.promise;
        await binding.destroy();
      } catch {
        // A generation aborted during import/initialize has no binding to
        // settle. Late initialize cleanup is handled by WidgetBinding.create.
      }
    });
    this.#generationCleanup = cleanup;
    return cleanup;
  }

  async #renderView(
    view: RuntimeView,
    requestedGeneration?: Generation,
  ): Promise<void> {
    if (view.signal.aborted || this.#controller.signal.aborted) {
      return;
    }
    const generation = requestedGeneration ?? this.#generation;
    const binding = generation
      ? await generation.promise
      : await this.#getCurrentBinding();
    const current = this.#generation;
    if (!current || current !== (generation ?? current)) {
      return;
    }
    if (view.generation === current) {
      return;
    }
    view.generation = current;
    try {
      await binding.createView({ el: view.el }, { signal: view.signal });
    } catch (error) {
      if (current !== this.#generation) {
        view.generation = undefined;
        return;
      }
      throw error;
    }
  }

  #mountStyle(view: RuntimeView): void {
    const root = view.el.getRootNode();
    // `instanceof` misses cross-realm roots (e.g. a Document
    // Picture-in-Picture window); the guards check realm-independent nodeType.
    if (!isDocument(root) && !isShadowRoot(root)) {
      return;
    }
    let mount = this.#styleMounts.get(root);
    if (!mount) {
      mount = createStyleMount(root, this.#css);
      this.#styleMounts.set(root, mount);
    }
    mount.references += 1;
    let released = false;
    const release = () => {
      if (released) {
        return;
      }
      released = true;
      const current = this.#styleMounts.get(root);
      if (!current) {
        return;
      }
      current.references -= 1;
      if (current.references === 0) {
        current.dispose();
        this.#styleMounts.delete(root);
      }
    };
    view.signal.addEventListener("abort", release, { once: true });
  }

  dispose(): void {
    if (this.#controller.signal.aborted) {
      return;
    }
    Logger.debug(`[WidgetRuntime] Disposing model=${this.#key}`);
    if (this.#modelTimeout) {
      clearTimeout(this.#modelTimeout);
      this.#modelTimeout = undefined;
    }
    if (this.#model.status === "pending") {
      this.#model.promise.catch(() => undefined);
      this.#model.reject(new Error("[anywidget] widget runtime destroyed"));
    }
    if (this.#generation) {
      void this.#queueGenerationCleanup(this.#generation);
    }
    this.#controller.abort();
    this.#views.clear();
    for (const mount of this.#styleMounts.values()) {
      mount.dispose();
    }
    this.#styleMounts.clear();
  }
}

function isDocument(node: Node): node is Document {
  return node.nodeType === Node.DOCUMENT_NODE;
}

function isShadowRoot(node: Node): node is ShadowRoot {
  return node.nodeType === Node.DOCUMENT_FRAGMENT_NODE && "host" in node;
}

function createStyleMount(root: StyleRoot, initialCss: string): StyleMount {
  // Build stylesheets in the root's own realm so they apply in a cross-realm
  // root (e.g. a Document Picture-in-Picture window).
  const doc = isDocument(root) ? root : (root.ownerDocument ?? document);
  const view = doc.defaultView ?? window;
  if (
    "adoptedStyleSheets" in root &&
    typeof view.CSSStyleSheet !== "undefined" &&
    typeof view.CSSStyleSheet.prototype.replaceSync === "function"
  ) {
    try {
      const sheet = new view.CSSStyleSheet();
      sheet.replaceSync(initialCss);
      root.adoptedStyleSheets = [...root.adoptedStyleSheets, sheet];
      return {
        references: 0,
        update(css) {
          sheet.replaceSync(css);
        },
        dispose() {
          root.adoptedStyleSheets = root.adoptedStyleSheets.filter(
            (candidate) => candidate !== sheet,
          );
        },
      };
    } catch {
      // Fall through to a style element when construction or parsing fails.
    }
  }

  const style = doc.createElement("style");
  style.textContent = initialCss;
  if (isDocument(root)) {
    doc.head.append(style);
  } else {
    root.append(style);
  }
  return {
    references: 0,
    update(css) {
      style.textContent = css;
    },
    dispose() {
      style.remove();
    },
  };
}
