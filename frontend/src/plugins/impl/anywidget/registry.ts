/* Copyright 2026 Marimo. All rights reserved. */
import type { NotificationMessageData } from "@/core/kernel/messages";
import { getRequestClient } from "@/core/network/requests";
import { isStaticNotebook } from "@/core/static/static-state";
import { assertNever } from "@/utils/assertNever";
import {
  type Base64String,
  base64ToDataView,
  dataViewToBase64,
} from "@/utils/json/base64";
import { Logger } from "@/utils/Logger";
import { repl } from "@/utils/repl";
import { viewStateAtom } from "@/core/mode";
import { store } from "@/core/state/jotai";
import { createHost, type WidgetResolver } from "./host";
import { getMarimoInternal, type MarimoComm, Model } from "./model";
import { WidgetRuntime } from "./runtime";
import { decodeFromWire, serializeBuffersToBase64 } from "./serialization";
import {
  isWidgetModelId,
  type EsmSpec,
  type ModelState,
  type WidgetModelId,
} from "./types";

/**
 * Only edit sessions may swap widget code ("present" is an edit
 * session with different chrome); a viewer's widget code is immutable.
 */
function defaultIsEditMode(): boolean {
  const mode = store.get(viewStateAtom).mode;
  return mode === "edit" || mode === "present";
}

/**
 * Maps model ids to stable runtimes and routes callers through their
 * public behavior. Generation and view lifecycles stay inside each runtime.
 */
export class WidgetRegistry implements WidgetResolver {
  #runtimes = new Map<WidgetModelId, WidgetRuntime>();
  #timeout: number;
  #isEditMode: () => boolean;

  constructor(timeout = 10_000, isEditMode: () => boolean = defaultIsEditMode) {
    this.#timeout = timeout;
    this.#isEditMode = isEditMode;
  }

  #getOrCreateRuntime(key: WidgetModelId): WidgetRuntime {
    let runtime = this.#runtimes.get(key);
    if (!runtime) {
      const nextRuntime = new WidgetRuntime(key, {
        timeout: this.#timeout,
        isEditMode: this.#isEditMode,
        createHost: (signal) => createHost(this, signal),
        onModelTimeout: () => {
          if (this.#runtimes.get(key) === nextRuntime) {
            nextRuntime.dispose();
            this.#runtimes.delete(key);
          }
        },
      });
      runtime = nextRuntime;
      this.#runtimes.set(key, runtime);
    }
    return runtime;
  }

  /**
   * Resolve the model for `key`, waiting for its `open` message if it
   * hasn't arrived yet. Rejects after the registry timeout so a ref to
   * a model that never opens fails loudly instead of hanging.
   */
  getModel(key: WidgetModelId): Promise<Model<ModelState>> {
    return this.#getOrCreateRuntime(key).getModel();
  }

  /**
   * Get a model synchronously if it exists and has been resolved.
   * Returns undefined if the model doesn't exist or is still pending.
   */
  getModelSync(key: WidgetModelId): Model<ModelState> | undefined {
    return this.#runtimes.get(key)?.getModelSync();
  }

  /**
   * Create a model with a managed lifecycle signal.
   * The signal is aborted when the entry is deleted.
   */
  createModel(
    key: WidgetModelId,
    factory: (signal: AbortSignal) => Model<ModelState>,
  ): void {
    this.#getOrCreateRuntime(key).createModel(factory);
  }

  setModel(key: WidgetModelId, model: Model<ModelState>): void {
    this.#getOrCreateRuntime(key).setModel(model);
  }

  /**
   * Record where this widget's code can be imported from and, in an
   * edit session, hot-swap a live generation whose code changed.
   *
   * Specs only come from kernel-authored notifications; model state
   * must never be treated as code (it is client-writable).
   */
  setSpec(key: WidgetModelId, spec: EsmSpec): void {
    this.#getOrCreateRuntime(key).setSpec(spec);
  }

  getWidget<T = unknown>(key: WidgetModelId) {
    return this.#getOrCreateRuntime(key).getWidget<T>();
  }

  createView(options: {
    modelId: WidgetModelId;
    el: HTMLElement;
    signal: AbortSignal;
  }): Promise<void> {
    return this.#getOrCreateRuntime(options.modelId).createView(options);
  }

  /**
   * Tear down everything known about `key`: the model's lifecycle
   * signal and the current generation.
   */
  delete(key: WidgetModelId): void {
    const runtime = this.#runtimes.get(key);
    if (!runtime) {
      return;
    }
    runtime.dispose();
    this.#runtimes.delete(key);
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
  const modelId = notification.model_id;
  if (!isWidgetModelId(modelId)) {
    throw new Error(`[anywidget] Invalid model id: ${String(modelId)}`);
  }
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
