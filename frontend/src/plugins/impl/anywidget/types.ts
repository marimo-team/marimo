/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-invalid-void-type */
/* eslint-disable @typescript-eslint/no-explicit-any */

// Copied from https://github.com/manzt/anywidget/blob/main/packages/types/index.ts
// with slight modifications
// - removed widget_manager
// We copy this for now since `@anywidget/types` pulls in jquery and backbone, which we don't need

type Awaitable<T> = T | Promise<T>;
export type EventHandler = (...args: any[]) => void;
type ObjectHash = Record<string, any>;
export type ChangeEventHandler<Payload> = (_: unknown, value: Payload) => void;
type LiteralUnion<T, U = string> = T | (U & {});

export interface AnyModel<T extends ObjectHash = ObjectHash> {
  get<K extends keyof T>(key: K): T[K];
  set<K extends keyof T>(key: K, value: T[K]): void;
  off<K extends keyof T>(
    eventName?: LiteralUnion<`change:${K & string}` | "msg:custom"> | null,
    callback?: EventHandler | null,
  ): void;
  on(
    eventName: "msg:custom",
    callback: (msg: any, buffers: DataView[]) => void,
  ): void;
  on<K extends `change:${keyof T & string}`>(
    eventName: K,
    callback: K extends `change:${infer Key}`
      ? ChangeEventHandler<T[Key]>
      : never,
  ): void;
  on(eventName: string, callback: EventHandler): void;
  save_changes(): void;
  send(
    content: any,
    callbacks?: any,
    buffers?: ArrayBuffer[] | ArrayBufferView[],
  ): void;
  widget_manager: {};
}

export interface Experimental {
  invoke: <T>(
    name: string,
    msg?: any,
    options?: {
      buffers?: DataView[];
      signal?: AbortSignal;
    },
  ) => Promise<[T, DataView[]]>;
}
export interface RenderProps<T extends ObjectHash = ObjectHash> {
  model: AnyModel<T>;
  el: HTMLElement;
  experimental: Experimental;
}
export type Render<T extends ObjectHash = ObjectHash> = (
  props: RenderProps<T>,
) => Awaitable<void | (() => Awaitable<void>)>;
export interface InitializeProps<T extends ObjectHash = ObjectHash> {
  model: AnyModel<T>;
  experimental: Experimental;
}

export type Initialize<T extends ObjectHash = ObjectHash> = (
  props: InitializeProps<T>,
) => Awaitable<void | (() => Awaitable<void>)>;
interface WidgetDef<T extends ObjectHash = ObjectHash> {
  initialize?: Initialize<T>;
  render?: Render<T>;
}
export type AnyWidget<T extends ObjectHash = ObjectHash> =
  | WidgetDef<T>
  | (() => Awaitable<WidgetDef<T>>);
