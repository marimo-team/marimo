/* Copyright 2026 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */

import type { AnyModel, AnyWidget, Experimental } from "@anywidget/types";
import { debounce } from "lodash-es";
import type { NotificationMessageData } from "@/core/kernel/messages";
import { getRequestClient } from "@/core/network/requests";
import {
  decodeFromWire,
  serializeBuffersToBase64,
} from "@/plugins/impl/anywidget/serialization";
import { assertNever } from "@/utils/assertNever";
import { Deferred } from "@/utils/Deferred";
import {
  type Base64String,
  base64ToDataView,
  dataViewToBase64,
} from "@/utils/json/base64";
import { Logger } from "@/utils/Logger";
import { repl } from "@/utils/repl";
import type { AnyWidgetMessage } from "./schemas";
import type { EventHandler, ModelState, WidgetModelId } from "./types";

class ModelManager {
  /**
   * Map of model ids to deferred promises
   */
  #models = new Map<WidgetModelId, Deferred<Model<ModelState>>>();
  /**
   * Timeout for model lookup
   */
  #timeout: number;

  constructor(timeout = 10_000) {
    this.#timeout = timeout;
  }

  get(key: WidgetModelId): Promise<Model<any>> {
    let deferred = this.#models.get(key);
    if (deferred) {
      return deferred.promise;
    }

    // If the model is not yet created, create the new deferred promise without resolving it
    deferred = new Deferred<Model<ModelState>>();
    this.#models.set(key, deferred);

    // Add timeout to prevent hanging
    setTimeout(() => {
      // Already settled
      if (deferred.status !== "pending") {
        return;
      }

      deferred.reject(new Error(`Model not found for key: ${key}`));
      this.#models.delete(key);
    }, this.#timeout);

    return deferred.promise;
  }

  set(key: WidgetModelId, model: Model<any>): void {
    let deferred = this.#models.get(key);
    if (!deferred) {
      deferred = new Deferred<Model<ModelState>>();
      this.#models.set(key, deferred);
    }
    deferred.resolve(model);
  }

  /**
   * Check if a model exists and has been resolved (not pending).
   * This is useful for checking if a model was already created by the plugin
   * before the 'open' message arrives.
   */
  has(key: WidgetModelId): boolean {
    const deferred = this.#models.get(key);
    return deferred !== undefined && deferred.status === "resolved";
  }

  /**
   * Get a model synchronously if it exists and has been resolved.
   * Returns undefined if the model doesn't exist or is still pending.
   */
  getSync(key: WidgetModelId): Model<any> | undefined {
    const deferred = this.#models.get(key);
    if (deferred && deferred.status === "resolved") {
      return deferred.value;
    }
    return undefined;
  }

  delete(key: WidgetModelId): void {
    this.#models.delete(key);
  }
}

interface MarimoComm<T> {
  sendUpdate: (value: Partial<T>) => Promise<void>;
  sendCustomMessage: (content: unknown, buffers: DataView[]) => Promise<void>;
}

const marimoSymbol = Symbol("marimo");

const experimental: Experimental = {
  invoke: async () => {
    const message =
      "anywidget.invoke not supported in marimo. Please file an issue at https://github.com/marimo-team/marimo/issues";
    Logger.warn(message);
    throw new Error(message);
  },
};

type RenderFn = (el: HTMLElement, signal: AbortSignal) => Promise<void>;

interface MarimoInternalApi<T extends ModelState> {
  /**
   * Resolve the widget definition and initialize if needed.
   * Returns a render function that can be called for each view.
   *
   * Per AFM spec:
   * - widgetDef() is called once per model
   * - initialize() is called once per model
   * - render() (the returned function) is called once per view
   */
  resolveWidget: (widgetDef: AnyWidget<T>) => Promise<RenderFn>;
  /**
   * Update model state and emit change events for any differences.
   */
  updateAndEmitDiffs: (value: T) => void;
  /**
   * Emit a custom message to listeners.
   */
  emitCustomMessage: (
    message: Extract<AnyWidgetMessage, { method: "custom" }>,
    buffers?: readonly DataView[],
  ) => void;
  /**
   * Destroy the model, triggering initialize cleanup.
   */
  destroy: () => void;
}

/**
 * Get the internal marimo API for a Model instance.
 * These are not part of the public AnyModel interface.
 */
export function getMarimoInternal<T extends ModelState>(
  model: Model<T>,
): MarimoInternalApi<T> {
  return model[marimoSymbol];
}

export const MODEL_MANAGER = new ModelManager();

export class Model<T extends ModelState> implements AnyModel<T> {
  #ANY_CHANGE_EVENT = "change";
  #dirtyFields: Map<keyof T, unknown>;
  #data: T;
  #comm: MarimoComm<T>;
  #listeners: Record<string, Set<EventHandler> | undefined> = {};
  #controller = new AbortController();
  #widgetDef: AnyWidget<T> | undefined;
  #render:
    | ((el: HTMLElement, signal: AbortSignal) => Promise<void>)
    | undefined;

  static _modelManager: ModelManager = MODEL_MANAGER;

  constructor(data: T, comm: MarimoComm<T>) {
    this.#data = data;
    this.#comm = comm;
    this.#dirtyFields = new Map();
  }

  /**
   * Internal marimo API - not part of AnyWidget AFM.
   * Access via getMarimoInternal().
   */
  [marimoSymbol]: MarimoInternalApi<T> = {
    updateAndEmitDiffs: (value: T) => this.#updateAndEmitDiffs(value),
    emitCustomMessage: (
      message: Extract<AnyWidgetMessage, { method: "custom" }>,
      buffers?: readonly DataView[],
    ) => this.#emitCustomMessage(message, buffers),
    resolveWidget: async (widgetDef: AnyWidget<T>): Promise<RenderFn> => {
      // Already initialized with the same widget - return cached render
      if (this.#render && this.#widgetDef === widgetDef) {
        return this.#render;
      }

      // If widgetDef changed (hot reload), destroy old and re-initialize
      if (this.#render && this.#widgetDef !== widgetDef) {
        this.#controller.abort();
        this.#controller = new AbortController();
        this.#render = undefined;
      }

      this.#widgetDef = widgetDef;

      // Resolve the widget definition (call if it's a function)
      const widget =
        typeof widgetDef === "function" ? await widgetDef() : widgetDef;

      // Call initialize once per model
      const cleanup = await widget.initialize?.({ model: this, experimental });
      if (cleanup) {
        this.#controller.signal.addEventListener("abort", cleanup);
      }

      // Store and return the render closure
      this.#render = async (el: HTMLElement, signal: AbortSignal) => {
        const renderCleanup = await widget.render?.({
          model: this,
          el,
          experimental,
        });
        if (renderCleanup) {
          // Cleanup when either the view unmounts or the model is destroyed
          AbortSignal.any([signal, this.#controller.signal]).addEventListener(
            "abort",
            renderCleanup,
          );
        }
      };

      return this.#render;
    },
    destroy: () => {
      this.#controller.abort();
    },
  };

  off(eventName?: string | null, callback?: EventHandler | null): void {
    if (!eventName) {
      this.#listeners = {};
      return;
    }

    if (!callback) {
      this.#listeners[eventName] = new Set();
      return;
    }

    this.#listeners[eventName]?.delete(callback);
  }

  send(
    content: any,
    callbacks?: any,
    buffers?: ArrayBuffer[] | ArrayBufferView[],
  ): Promise<void> {
    const dataViews = (buffers ?? []).map((buf) =>
      buf instanceof ArrayBuffer
        ? new DataView(buf)
        : new DataView(buf.buffer, buf.byteOffset, buf.byteLength),
    );
    return this.#comm
      .sendCustomMessage(content, dataViews)
      .then(() => callbacks?.());
  }

  widget_manager = {
    async get_model<TT extends ModelState>(
      model_id: WidgetModelId,
    ): Promise<AnyModel<TT>> {
      const model = await Model._modelManager.get(model_id);
      if (!model) {
        throw new Error(
          `Model not found with id: ${model_id}. This is likely because the model was not registered.`,
        );
      }
      return model;
    },
  };

  get<K extends keyof T>(key: K): T[K] {
    return this.#data[key];
  }

  set<K extends keyof T>(key: K, value: T[K]): void {
    this.#data = { ...this.#data, [key]: value };
    this.#dirtyFields.set(key, value);
    this.#emit(`change:${key as K & string}`, value);
    this.#emitAnyChange();
  }

  save_changes(): void {
    if (this.#dirtyFields.size === 0) {
      return;
    }
    // Only send the dirty fields, not the entire state.
    const partialData = Object.fromEntries(
      this.#dirtyFields.entries(),
    ) as Partial<T>;

    // Clear the dirty fields to avoid sending again.
    this.#dirtyFields.clear();
    this.#comm.sendUpdate(partialData);
  }

  on(eventName: string, callback: EventHandler): void {
    if (!this.#listeners[eventName]) {
      this.#listeners[eventName] = new Set();
    }
    this.#listeners[eventName].add(callback);
  }

  #emit<K extends keyof T>(event: `change:${K & string}`, value: T[K]) {
    if (!this.#listeners[event]) {
      return;
    }
    const listeners = this.#listeners[event];
    for (const listener of listeners) {
      try {
        listener(value);
      } catch (error) {
        Logger.error("Error emitting event", error);
      }
    }
  }

  #updateAndEmitDiffs(value: T) {
    if (value == null) {
      return;
    }

    Object.keys(value).forEach((key) => {
      const k = key as keyof T;
      // Shallow equal since these can be large objects
      if (this.#data[k] !== value[k]) {
        this.set(k, value[k]);
      }
    });
  }

  /**
   * When receiving a message from the backend.
   * We want to notify all listeners with `msg:custom`
   */
  #emitCustomMessage(
    message: Extract<AnyWidgetMessage, { method: "custom" }>,
    buffers: readonly DataView[] = [],
  ) {
    const listeners = this.#listeners["msg:custom"];
    if (!listeners) {
      return;
    }
    for (const listener of listeners) {
      try {
        listener(message.content, buffers);
      } catch (error) {
        Logger.error("Error emitting event", error);
      }
    }
  }

  // Debounce 0 to send off one request in a single frame
  #emitAnyChange = debounce(() => {
    const listeners = this.#listeners[this.#ANY_CHANGE_EVENT];
    if (!listeners) {
      return;
    }
    for (const listener of listeners) {
      try {
        listener();
      } catch (error) {
        Logger.error("Error emitting event", error);
      }
    }
  }, 0);
}

/**
 * Handle an incoming model lifecycle notification from the backend.
 *
 * Messages are dispatched by method type:
 * - "open": Initialize a new model or update existing one with initial state
 * - "update": Update model state with new values
 * - "custom": Forward custom message to model listeners
 * - "close": Remove model from manager
 */
export async function handleWidgetMessage(
  modelManager: ModelManager,
  notification: NotificationMessageData<"model-lifecycle">,
): Promise<void> {
  const modelId = notification.model_id as WidgetModelId;
  const msg = notification.message;

  Logger.debug("AnyWidget message", msg);

  // Decode base64 buffers to DataViews (present in open/update/custom messages)
  const base64Buffers: Base64String[] =
    "buffers" in msg ? (msg.buffers as Base64String[]) : [];
  const buffers = base64Buffers.map(base64ToDataView);

  switch (msg.method) {
    case "open": {
      const { state, buffer_paths = [] } = msg;
      const stateWithBuffers = decodeFromWire({
        state,
        bufferPaths: buffer_paths,
        buffers,
      });

      // Check if a model already exists (created by the plugin using model_id reference)
      // If so, just update its state instead of creating a duplicate
      const existingModel = modelManager.getSync(modelId);
      if (existingModel) {
        getMarimoInternal(existingModel).updateAndEmitDiffs(stateWithBuffers);
        return;
      }

      const model = new Model(stateWithBuffers, {
        async sendUpdate(changeData) {
          const { state, buffers, bufferPaths } =
            serializeBuffersToBase64(changeData);
          await getRequestClient().sendModelValue({
            modelId,
            message: { method: "update", state, bufferPaths },
            buffers,
          });
        },
        async sendCustomMessage(content, buffers) {
          await getRequestClient().sendModelValue({
            modelId,
            message: { method: "custom", content },
            buffers: buffers.map(dataViewToBase64),
          });
        },
      });
      modelManager.set(modelId, model);
      return;
    }

    case "custom": {
      const model = await modelManager.get(modelId);
      // For custom messages, we need to reconstruct the AnyWidgetMessage format
      getMarimoInternal(model).emitCustomMessage(
        { method: "custom", content: msg.content },
        buffers,
      );
      return;
    }

    case "close": {
      const model = modelManager.getSync(modelId);
      if (model) {
        getMarimoInternal(model).destroy();
      }
      modelManager.delete(modelId);
      return;
    }

    case "update": {
      const { state, buffer_paths = [] } = msg;
      const stateWithBuffers = decodeFromWire({
        state,
        bufferPaths: buffer_paths,
        buffers,
      });
      const model = await modelManager.get(modelId);
      getMarimoInternal(model).updateAndEmitDiffs(stateWithBuffers);
      return;
    }

    default:
      assertNever(msg);
  }
}

repl(MODEL_MANAGER, "MODEL_MANAGER");

export const visibleForTesting = {
  ModelManager,
};
