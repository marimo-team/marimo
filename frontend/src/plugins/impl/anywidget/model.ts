/* Copyright 2026 Marimo. All rights reserved. */
/* oxlint-disable typescript/no-explicit-any */

import type { AnyModel } from "@anywidget/types";
import { debounce } from "lodash-es";
import { Logger } from "@/utils/Logger";
import type { EventHandler, ModelState, WidgetModelId } from "./types";

/**
 * The custom-message shape delivered to `msg:custom` listeners — the
 * only message shape the frontend re-declares; the wire contract is
 * the generated `model-lifecycle` type.
 */
export interface CustomMessage {
  method: "custom";
  // oxlint-disable-next-line typescript/no-explicit-any
  content: any;
}

/**
 * The model's channel back to the kernel; a no-op in static exports.
 */
export interface MarimoComm<T> {
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
    message: CustomMessage,
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

export class Model<T extends ModelState> implements AnyModel<T> {
  #ANY_CHANGE_EVENT = "change";
  #dirtyFields: Map<keyof T, unknown>;
  #data: T;
  #comm: MarimoComm<T>;
  #listeners: Record<string, Set<EventHandler> | undefined> = {};

  /**
   * Resolves models for the legacy ipywidgets escape hatch
   * (`widget_manager.get_model`). Assigned by the registry module at
   * import time to avoid an import cycle.
   */
  static _modelManager: {
    getModel(model_id: WidgetModelId): Promise<Model<any>>;
  };

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
      message: CustomMessage,
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
      const model = await Model._modelManager.getModel(model_id);
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

  /**
   * Register an event listener.
   *
   * Passing `signal` ties the listener's lifetime to an `AbortSignal` —
   * when the signal aborts, the listener is auto-removed. This is the
   * preferred cleanup mechanism (matches the web platform pattern of
   * `addEventListener({ signal })`) and is what `modelProxy` uses to
   * scope listeners to view / binding lifetimes.
   */
  on(
    eventName: string,
    callback: EventHandler,
    options?: { signal?: AbortSignal },
  ): void {
    const signal = options?.signal;
    if (signal?.aborted) {
      return;
    }
    if (!this.#listeners[eventName]) {
      this.#listeners[eventName] = new Set();
    }
    this.#listeners[eventName].add(callback);
    signal?.addEventListener("abort", () => this.off(eventName, callback), {
      once: true,
    });
  }

  #emit<K extends keyof T>(event: `change:${K & string}`, value: T[K]) {
    const listeners = this.#listeners[event];
    if (!listeners) {
      return;
    }
    // Snapshot before iterating: a callback may unregister itself
    // (typical signal-based abort handler calling `model.off`), and a
    // Set mutated mid-iteration drops the very next element.
    // oxlint-disable-next-line no-useless-spread -- snapshot is intentional
    for (const listener of [...listeners]) {
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
    message: CustomMessage,
    buffers: readonly DataView[] = [],
  ) {
    const listeners = this.#listeners["msg:custom"];
    if (!listeners) {
      return;
    }
    // Snapshot before iterating: see `#emit` for rationale.
    // oxlint-disable-next-line no-useless-spread -- snapshot is intentional
    for (const listener of [...listeners]) {
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
    // Snapshot before iterating: see `#emit` for rationale.
    // oxlint-disable-next-line no-useless-spread -- snapshot is intentional
    for (const listener of [...listeners]) {
      try {
        listener();
      } catch (error) {
        Logger.error("Error emitting event", error);
      }
    }
  }, 0);
}
