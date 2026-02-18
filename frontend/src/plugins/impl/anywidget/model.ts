/* Copyright 2026 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */

import type { AnyModel } from "@anywidget/types";
import { debounce } from "lodash-es";
import type { NotificationMessageData } from "@/core/kernel/messages";
import { getRequestClient } from "@/core/network/requests";
import { isStaticNotebook } from "@/core/static/static-state";
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
import { BINDING_MANAGER } from "./widget-binding";

interface ModelEntry {
  deferred: Deferred<Model<ModelState>>;
  controller: AbortController;
}

class ModelManager {
  #entries = new Map<WidgetModelId, ModelEntry>();
  #timeout: number;

  constructor(timeout = 10_000) {
    this.#timeout = timeout;
  }

  #getOrCreateEntry(key: WidgetModelId): ModelEntry {
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

  get(key: WidgetModelId): Promise<Model<any>> {
    const entry = this.#getOrCreateEntry(key);
    if (entry.deferred.status === "pending") {
      // Add timeout to prevent hanging
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
   * Create a model with a managed lifecycle signal.
   * The signal is aborted when the model is deleted.
   */
  create(
    key: WidgetModelId,
    factory: (signal: AbortSignal) => Model<ModelState>,
  ): void {
    const entry = this.#getOrCreateEntry(key);
    entry.deferred.resolve(factory(entry.controller.signal));
  }

  set(key: WidgetModelId, model: Model<any>): void {
    this.#getOrCreateEntry(key).deferred.resolve(model);
  }

  /**
   * Get a model synchronously if it exists and has been resolved.
   * Returns undefined if the model doesn't exist or is still pending.
   */
  getSync(key: WidgetModelId): Model<any> | undefined {
    const entry = this.#entries.get(key);
    if (entry && entry.deferred.status === "resolved") {
      return entry.deferred.value;
    }
    return undefined;
  }

  delete(key: WidgetModelId): void {
    Logger.debug(
      `[ModelManager] Deleting model=${key}, aborting lifecycle signal`,
    );
    this.#entries.get(key)?.controller.abort();
    this.#entries.delete(key);
  }
}

interface MarimoComm<T> {
  sendUpdate: (value: Partial<T>) => Promise<void>;
  sendCustomMessage: (content: unknown, buffers: DataView[]) => Promise<void>;
}

const marimoSymbol = Symbol("marimo");

interface MarimoInternalApi<T extends ModelState> {
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

  static _modelManager: ModelManager = MODEL_MANAGER;

  constructor(data: T, comm: MarimoComm<T>, signal?: AbortSignal) {
    this.#data = data;
    this.#comm = comm;
    this.#dirtyFields = new Map();
    if (signal) {
      signal.addEventListener("abort", () => {
        Logger.debug("[Model] Signal aborted, clearing all listeners");
        this.#listeners = {};
      });
    }
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

      modelManager.create(modelId, (signal) => {
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
      const model = await modelManager.get(modelId);
      // For custom messages, we need to reconstruct the AnyWidgetMessage format
      getMarimoInternal(model).emitCustomMessage(
        { method: "custom", content: msg.content },
        buffers,
      );
      return;
    }

    case "close":
      BINDING_MANAGER.destroy(modelId);
      modelManager.delete(modelId); // aborts the model's signal, clearing listeners
      return;

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
