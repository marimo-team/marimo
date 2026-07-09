/* Copyright 2026 Marimo. All rights reserved. */
/* oxlint-disable typescript/no-explicit-any */

import type { NotificationMessageData } from "@/core/kernel/messages";
import { getRequestClient } from "@/core/network/requests";
import { isStaticNotebook } from "@/core/static/static-state";
import { assertNever } from "@/utils/assertNever";
import { Deferred } from "@/utils/Deferred";
import {
  type Base64String,
  base64ToDataView,
  dataViewToBase64,
} from "@/utils/json/base64";
import { Logger } from "@/utils/Logger";
import { repl } from "@/utils/repl";
import { viewStateAtom } from "@/core/mode";
import { store } from "@/core/state/jotai";
import { getMarimoInternal, type MarimoComm, Model } from "./model";
import {
  getInvalidAnyWidgetModuleError,
  resolveAnyWidget,
} from "./resolve-widget";
import { decodeFromWire, serializeBuffersToBase64 } from "./serialization";
import type { EsmSpec, ModelState, WidgetModelId } from "./types";
import { WIDGET_DEF_REGISTRY, WidgetBinding } from "./widget-binding";

/**
 * One generation of a widget's binding. The controller tears it down,
 * aborting an in-flight `initialize` if creation hasn't settled.
 */
interface Generation {
  hash: string;
  controller: AbortController;
  promise: Promise<WidgetBinding<any>>;
}

/**
 * Everything the registry knows about one widget, keyed by model id.
 */
interface RegistryEntry {
  deferred: Deferred<Model<ModelState>>;
  controller: AbortController;
  esmSpec?: EsmSpec;
  generation?: Generation;
}

/**
 * Only edit sessions may swap widget code ("present" is an edit
 * session with different chrome); a viewer's widget code is immutable.
 */
function defaultIsEditMode(): boolean {
  const mode = store.get(viewStateAtom).mode;
  return mode === "edit" || mode === "present";
}

/**
 * The single owner of widget models, specs, and bindings, serving the
 * React plugin and `host.getWidget` alike.
 */
export class WidgetRegistry {
  #entries = new Map<WidgetModelId, RegistryEntry>();
  #timeout: number;
  #isEditMode: () => boolean;

  constructor(timeout = 10_000, isEditMode: () => boolean = defaultIsEditMode) {
    this.#timeout = timeout;
    this.#isEditMode = isEditMode;
  }

  #getOrCreateEntry(key: WidgetModelId): RegistryEntry {
    let entry = this.#entries.get(key);
    if (!entry) {
      entry = {
        deferred: new Deferred<Model<ModelState>>(),
        controller: new AbortController(),
      };
      this.#entries.set(key, entry);
    }
    return entry;
  }

  /**
   * Resolve the model for `key`, waiting for its `open` message if it
   * hasn't arrived yet. Rejects after the registry timeout so a ref to
   * a model that never opens fails loudly instead of hanging.
   */
  getModel(key: WidgetModelId): Promise<Model<any>> {
    const entry = this.#getOrCreateEntry(key);
    if (entry.deferred.status === "pending") {
      setTimeout(() => {
        if (entry.deferred.status !== "pending") {
          return;
        }
        entry.deferred.reject(new Error(`Model not found for key: ${key}`));
        this.#entries.delete(key);
      }, this.#timeout);
    }
    return entry.deferred.promise;
  }

  /**
   * Get a model synchronously if it exists and has been resolved.
   * Returns undefined if the model doesn't exist or is still pending.
   */
  getModelSync(key: WidgetModelId): Model<any> | undefined {
    const entry = this.#entries.get(key);
    if (entry && entry.deferred.status === "resolved") {
      return entry.deferred.value;
    }
    return undefined;
  }

  /**
   * Create a model with a managed lifecycle signal.
   * The signal is aborted when the entry is deleted.
   */
  createModel(
    key: WidgetModelId,
    factory: (signal: AbortSignal) => Model<ModelState>,
  ): void {
    const entry = this.#getOrCreateEntry(key);
    entry.deferred.resolve(factory(entry.controller.signal));
  }

  setModel(key: WidgetModelId, model: Model<any>): void {
    this.#getOrCreateEntry(key).deferred.resolve(model);
  }

  /**
   * Record where this widget's code can be imported from and, in an
   * edit session, hot-swap a live generation whose code changed.
   *
   * Specs only come from kernel-authored notifications; model state
   * must never be treated as code (it is client-writable).
   */
  setSpec(key: WidgetModelId, spec: EsmSpec): void {
    const entry = this.#getOrCreateEntry(key);
    entry.esmSpec = spec;
    // Outside edit sessions the spec is only recorded, becoming what
    // future generations are built from.
    if (
      entry.generation &&
      entry.generation.hash !== spec.hash &&
      this.#isEditMode()
    ) {
      this.#swapGeneration(key, entry, spec);
    }
  }

  /**
   * Import a spec's module, resolve the widget, and run `initialize`.
   */
  async #createBinding(
    spec: EsmSpec,
    model: Model<any>,
    controller: AbortController,
  ): Promise<WidgetBinding<any>> {
    const mod = await WIDGET_DEF_REGISTRY.getModule(spec.url, spec.hash, {
      kernelAuthored: true,
    });
    const widget = resolveAnyWidget(mod, spec.url);
    if (!widget) {
      throw getInvalidAnyWidgetModuleError(mod, spec.url);
    }
    return WidgetBinding.create(widget, model, controller);
  }

  #startGeneration(
    entry: RegistryEntry,
    spec: EsmSpec,
    model: Model<any>,
  ): Generation {
    const controller = new AbortController();
    const generation: Generation = {
      hash: spec.hash,
      controller,
      promise: this.#createBinding(spec, model, controller),
    };
    // A failed generation must not poison the entry; the next
    // getWidget retries from the current spec.
    generation.promise.catch(() => {
      if (entry.generation === generation) {
        entry.generation = undefined;
      }
    });
    entry.generation = generation;
    return generation;
  }

  /**
   * Hot reload: destroy the live generation (cleanups run, listeners
   * clear), create the next one against the same model, and re-render
   * its views in place. Model state persists.
   */
  #swapGeneration(
    key: WidgetModelId,
    entry: RegistryEntry,
    spec: EsmSpec,
  ): void {
    const previous = entry.generation;
    if (!previous) {
      return;
    }
    Logger.debug(`[WidgetRegistry] Hot-swapping generation for model=${key}`);
    const controller = new AbortController();
    const generation: Generation = {
      hash: spec.hash,
      controller,
      promise: (async () => {
        // A failed old generation just means nothing to destroy.
        const old = await previous.promise.catch(() => undefined);
        const views = old ? old.liveViews : [];
        previous.controller.abort();
        const model = await entry.deferred.promise;
        const next = await this.#createBinding(spec, model, controller);
        for (const view of views) {
          if (view.signal.aborted) {
            continue;
          }
          void next.createView(
            { el: view.el },
            { signal: view.signal, host: view.host },
          );
        }
        return next;
      })(),
    };
    generation.promise.catch(() => {
      if (entry.generation === generation) {
        entry.generation = undefined;
      }
    });
    entry.generation = generation;
  }

  /**
   * Resolve the fully-initialized widget for `key`: its model and the
   * current binding generation, `initialize` settled. The first caller
   * starts the generation; everyone else awaits the same promise. A
   * model without a spec has no code anywhere, so that fails fast.
   */
  async getWidget(
    key: WidgetModelId,
  ): Promise<{ model: Model<any>; binding: WidgetBinding<any> }> {
    const model = await this.getModel(key);
    const entry = this.#getOrCreateEntry(key);
    if (!entry.generation) {
      const spec = entry.esmSpec;
      if (!spec) {
        throw new Error(
          `[anywidget] No ESM spec for model ${key}: ` +
            "nothing ever provided this widget's code",
        );
      }
      this.#startGeneration(entry, spec, model);
    }
    // Non-null: set above or already present.
    const generation = entry.generation as Generation;
    return { model, binding: await generation.promise };
  }

  /**
   * Tear down everything known about `key`: the model's lifecycle
   * signal and the current generation.
   */
  delete(key: WidgetModelId): void {
    Logger.debug(`[WidgetRegistry] Deleting entry for model=${key}`);
    const entry = this.#entries.get(key);
    if (!entry) {
      return;
    }
    entry.generation?.controller.abort();
    // Destroyed-mid-initialize rejections reach awaiting callers but
    // must not surface as unhandled here.
    entry.generation?.promise.catch(() => undefined);
    entry.controller.abort();
    this.#entries.delete(key);
  }
}

export const WIDGET_REGISTRY = new WidgetRegistry();

// The legacy ipywidgets escape hatch (`model.widget_manager.get_model`)
// resolves through the registry; assigned here to keep Model free of
// registry knowledge.
Model._modelManager = WIDGET_REGISTRY;

/**
 * Handle an incoming model lifecycle notification from the backend.
 *
 * Messages are dispatched by method type:
 * - "open": Initialize a new model or update existing one with initial state
 * - "update": Update model state with new values
 * - "custom": Forward custom message to model listeners
 * - "close": Remove the model and its binding from the registry
 */
export async function handleWidgetMessage(
  registry: WidgetRegistry,
  notification: NotificationMessageData<"model-lifecycle">,
): Promise<void> {
  const modelId = notification.model_id as WidgetModelId;
  const msg = notification.message;

  // Decode base64 buffers to DataViews (present in open/update/custom messages)
  const base64Buffers: Base64String[] = "buffers" in msg ? msg.buffers : [];
  const buffers = base64Buffers.map(base64ToDataView);

  switch (msg.method) {
    case "open": {
      const { state, buffer_paths = [] } = msg;
      // Record the spec before resolving the model so a waiting
      // getWidget sees it.
      if (msg.esm_spec) {
        registry.setSpec(modelId, msg.esm_spec);
      }
      const stateWithBuffers = decodeFromWire({
        state,
        bufferPaths: buffer_paths,
        buffers,
      });

      // Check if a model already exists (created by the plugin using model_id reference)
      // If so, just update its state instead of creating a duplicate
      const existingModel = registry.getModelSync(modelId);
      if (existingModel) {
        getMarimoInternal(existingModel).updateAndEmitDiffs(stateWithBuffers);
        return;
      }

      registry.createModel(modelId, (signal) => {
        // In static exports there is no kernel, so comm calls are no-ops.
        const comm: MarimoComm<ModelState> = isStaticNotebook()
          ? {
              sendUpdate: async () => undefined,
              sendCustomMessage: async () => undefined,
            }
          : {
              async sendUpdate(changeData) {
                if (signal.aborted) {
                  Logger.debug(
                    `[Model] sendUpdate suppressed for model=${modelId} (signal aborted)`,
                  );
                  return;
                }
                const { state, buffers, bufferPaths } =
                  serializeBuffersToBase64(changeData);
                await getRequestClient().sendModelValue({
                  modelId,
                  message: { method: "update", state, bufferPaths },
                  buffers,
                });
              },
              async sendCustomMessage(content, buffers) {
                if (signal.aborted) {
                  Logger.debug(
                    `[Model] sendCustomMessage suppressed for model=${modelId} (signal aborted)`,
                  );
                  return;
                }
                await getRequestClient().sendModelValue({
                  modelId,
                  message: { method: "custom", content },
                  buffers: buffers.map(dataViewToBase64),
                });
              },
            };

        return new Model(stateWithBuffers, comm, signal);
      });
      return;
    }

    case "custom": {
      const model = await registry.getModel(modelId);
      // For custom messages, we need to reconstruct the custom-message shape
      getMarimoInternal(model).emitCustomMessage(
        { method: "custom", content: msg.content },
        buffers,
      );
      return;
    }

    case "close":
      registry.delete(modelId); // aborts the model's signal, destroys the binding
      return;

    case "update": {
      const { state, buffer_paths = [] } = msg;
      // A spec on an update is a hot reload (handled by setSpec).
      if (msg.esm_spec) {
        registry.setSpec(modelId, msg.esm_spec);
      }
      const stateWithBuffers = decodeFromWire({
        state,
        bufferPaths: buffer_paths,
        buffers,
      });
      const model = await registry.getModel(modelId);
      getMarimoInternal(model).updateAndEmitDiffs(stateWithBuffers);
      return;
    }

    default:
      assertNever(msg);
  }
}

repl(WIDGET_REGISTRY, "WIDGET_REGISTRY");
