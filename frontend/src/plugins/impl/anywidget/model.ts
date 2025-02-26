/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { Logger } from "@/utils/Logger";
import type { AnyModel } from "@anywidget/types";
import { dequal } from "dequal";
import { debounce } from "lodash-es";
import { z } from "zod";

export type EventHandler = (...args: any[]) => void;

export class Model<T extends Record<string, any>> implements AnyModel<T> {
  private ANY_CHANGE_EVENT = "change";

  constructor(
    private data: T,
    private onChange: (value: Partial<T>) => void,
    private sendToWidget: (req: { content?: any }) => Promise<null | undefined>,
  ) {}

  private dirtyFields = new Set<keyof T>();
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
    this.sendToWidget({ content }).then(callbacks);
  }

  widget_manager = {
    get_model<TT extends Record<string, any>>(
      _model_id: string,
    ): Promise<AnyModel<TT>> {
      Logger.warn("widget_manager not supported in marimo");
      return Promise.resolve(this as unknown as AnyModel<TT>);
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
    this.dirtyFields.clear();
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
    const response = WidgetMessageSchema.safeParse(message);
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

const WidgetMessageSchema = z.union([
  z.object({
    method: z.literal("update"),
    state: z.record(z.any()),
  }),
  z.object({
    method: z.literal("custom"),
    content: z.any(),
  }),
  z.object({
    method: z.literal("echo_update"),
    buffer_paths: z.array(z.array(z.union([z.string(), z.number()]))),
    state: z.record(z.any()),
  }),
]);
