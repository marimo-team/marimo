/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { sendModelValue } from "@/core/network/requests";
import { assertNever } from "@/utils/assertNever";
import { updateBufferPaths } from "@/utils/data-views";
import { Deferred } from "@/utils/Deferred";
import { throwNotImplemented } from "@/utils/functions";
import type { Base64String } from "@/utils/json/base64";
import { Logger } from "@/utils/Logger";
import type { AnyModel } from "@anywidget/types";
import { dequal } from "dequal";
import { debounce } from "lodash-es";
import { z } from "zod";

export type EventHandler = (...args: any[]) => void;

class ModelManager {
  private models = new Map<string, Deferred<Model<any>>>();

  constructor(private timeout = 10_000) {}

  get(key: string): Promise<Model<any>> {
    let deferred = this.models.get(key);
    if (deferred) {
      return deferred.promise;
    }

    // If the model is not yet created, create the new deferred promise without resolving it
    deferred = new Deferred<Model<any>>();
    this.models.set(key, deferred);

    // Add timeout to prevent hanging
    setTimeout(() => {
      // Already settled
      if (deferred.status !== "pending") {
        return;
      }

      deferred.reject(new Error(`Model not found for key: ${key}`));
      this.models.delete(key);
    }, this.timeout);

    return deferred.promise;
  }

  set(key: string, model: Model<any>): void {
    let deferred = this.models.get(key);
    if (!deferred) {
      deferred = new Deferred<Model<any>>();
      this.models.set(key, deferred);
    }
    deferred.resolve(model);
  }

  delete(key: string): void {
    this.models.delete(key);
  }
}

export const MODEL_MANAGER = new ModelManager();

export class Model<T extends Record<string, any>> implements AnyModel<T> {
  private ANY_CHANGE_EVENT = "change";
  private dirtyFields;
  public static _modelManager: ModelManager = MODEL_MANAGER;

  constructor(
    private data: T,
    private onChange: (value: Partial<T>) => void,
    private sendToWidget: (req: {
      content?: any;
      buffers?: ArrayBuffer[] | ArrayBufferView[];
    }) => Promise<null | undefined>,
    initialDirtyFields: Set<keyof T>,
  ) {
    this.dirtyFields = new Set(initialDirtyFields);
  }

  private listeners: Record<string, Set<EventHandler>> = {};

  off(eventName?: string | null, callback?: EventHandler | null): void {
    if (!eventName) {
      this.listeners = {};
      return;
    }

    if (!callback) {
      this.listeners[eventName] = new Set();
      return;
    }

    this.listeners[eventName]?.delete(callback);
  }

  send(
    content: any,
    callbacks?: any,
    buffers?: ArrayBuffer[] | ArrayBufferView[],
  ): void {
    if (buffers) {
      Logger.warn("buffers not supported in marimo anywidget.send");
    }
    this.sendToWidget({ content, buffers }).then(callbacks);
  }

  widget_manager = {
    async get_model<TT extends Record<string, any>>(
      model_id: string,
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
    return this.data[key];
  }

  set<K extends keyof T>(key: K, value: T[K]): void {
    this.data = { ...this.data, [key]: value };
    this.dirtyFields.add(key);
    this.emit(`change:${key as K & string}`, value);
    this.emitAnyChange();
  }

  save_changes(): void {
    if (this.dirtyFields.size === 0) {
      return;
    }
    const partialData: Partial<T> = {};
    this.dirtyFields.forEach((key) => {
      partialData[key] = this.data[key];
    });
    // We don't clear the dirty fields here, because we want
    // to send all fields that different from the initial value (have ever been changed).
    // This is less performant, but more correct, because the backend
    // stores the last value sent, and not a merge of the values.
    // When the backend knows to merge the partial updates, then we can clear
    // the dirty fields.
    // this.dirtyFields.clear();
    this.onChange(partialData);
  }

  updateAndEmitDiffs(value: T): void {
    Object.keys(value).forEach((key) => {
      const k = key as keyof T;
      if (!dequal(this.data[k], value[k])) {
        this.set(k, value[k]);
      }
    });
  }

  /**
   * When receiving a message from the backend.
   * We want to notify all listeners with `msg:custom`
   */
  receiveCustomMessage(message: any, buffers?: DataView[]): void {
    const response = AnyWidgetMessageSchema.safeParse(message);
    if (response.success) {
      const data = response.data;
      switch (data.method) {
        case "update":
          this.updateAndEmitDiffs(data.state as T);
          break;
        case "custom":
          this.listeners["msg:custom"]?.forEach((cb) =>
            cb(data.content, buffers),
          );
          break;
        case "open":
          this.updateAndEmitDiffs(data.state as T);
          break;
      }
    } else {
      Logger.error("Failed to parse message", response.error);
      Logger.error("Message", message);
    }
  }

  on(eventName: string, callback: EventHandler): void {
    if (!this.listeners[eventName]) {
      this.listeners[eventName] = new Set();
    }
    this.listeners[eventName].add(callback);
  }

  private emit<K extends keyof T>(event: `change:${K & string}`, value: T[K]) {
    if (!this.listeners[event]) {
      return;
    }
    this.listeners[event].forEach((cb) => cb(value));
  }

  // Debounce 0 to send off one request in a single frame
  private emitAnyChange = debounce(() => {
    this.listeners[this.ANY_CHANGE_EVENT]?.forEach((cb) => cb());
  }, 0);
}

const BufferPathSchema = z.array(z.array(z.union([z.string(), z.number()])));
const StateSchema = z.record(z.any());

const AnyWidgetMessageSchema = z.discriminatedUnion("method", [
  z.object({
    method: z.literal("open"),
    state: StateSchema,
    buffer_paths: BufferPathSchema.optional(),
  }),
  z.object({
    method: z.literal("update"),
    state: StateSchema,
    buffer_paths: BufferPathSchema.optional(),
  }),
  z.object({
    method: z.literal("custom"),
    content: z.any(),
  }),
  z.object({
    method: z.literal("echo_update"),
    buffer_paths: BufferPathSchema,
    state: StateSchema,
  }),
  z.object({
    method: z.literal("close"),
  }),
]);

export type AnyWidgetMessage = z.infer<typeof AnyWidgetMessageSchema>;

export function isMessageWidgetState(msg: unknown): msg is AnyWidgetMessage {
  if (msg == null) {
    return false;
  }

  return AnyWidgetMessageSchema.safeParse(msg).success;
}

export async function handleWidgetMessage(
  modelId: string,
  msg: AnyWidgetMessage,
  buffers: Base64String[],
  modelManager: ModelManager,
): Promise<void> {
  if (msg.method === "echo_update") {
    // We don't need to do anything with this message
    return;
  }

  if (msg.method === "custom") {
    const model = await modelManager.get(modelId);
    model.receiveCustomMessage(msg.content);
    return;
  }

  if (msg.method === "close") {
    modelManager.delete(modelId);
    return;
  }

  const { method, state, buffer_paths = [] } = msg;
  const stateWithBuffers = updateBufferPaths(state, buffer_paths, buffers);

  if (method === "open") {
    const handleDataChange = (changeData: Record<string, any>) => {
      if (buffer_paths) {
        Logger.warn(
          "Changed data with buffer paths may not be supported",
          changeData,
        );
        // TODO: we may want to extract/undo DataView, to get back buffers and buffer_paths
      }
      sendModelValue({
        modelId: modelId,
        message: {
          state: changeData,
          bufferPaths: [],
        },
        buffers: [],
      });
    };

    const model = new Model(
      stateWithBuffers,
      handleDataChange,
      throwNotImplemented,
      new Set(),
    );
    modelManager.set(modelId, model);
    return;
  }

  if (method === "update") {
    const model = await modelManager.get(modelId);
    model.updateAndEmitDiffs(stateWithBuffers);
    return;
  }

  assertNever(method);
}

export const visibleForTesting = {
  ModelManager,
};
