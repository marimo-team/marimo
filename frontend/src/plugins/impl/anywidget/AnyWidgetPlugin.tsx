/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { z } from "zod";
import type { AnyWidget, AnyModel, Initialize, Render } from "@anywidget/types";

import type { IPluginProps } from "@/plugins/types";
import { useEffect, useRef } from "react";
import { useAsyncData } from "@/hooks/useAsyncData";
import { dequal } from "dequal";
import { useOnMount } from "@/hooks/useLifecycle";
import { useDeepCompareMemoize } from "@/hooks/useDeepCompareMemoize";
import { ErrorBanner } from "../common/error-banner";
import { createPlugin } from "@/plugins/core/builder";
import { rpc } from "@/plugins/core/rpc";
import type { EventHandler } from "./types";
import { Logger } from "@/utils/Logger";
import { useEventListener } from "@/hooks/useEventListener";
import { MarimoIncomingMessageEvent } from "@/core/dom/events";

interface Data {
  jsUrl: string;
  css?: string | null;
}

type T = Record<string, any>;

// eslint-disable-next-line @typescript-eslint/consistent-type-definitions
type PluginFunctions = {
  send_to_widget: <T>(req: {
    content?: any;
  }) => Promise<null | undefined>;
};

export const AnyWidgetPlugin = createPlugin<T>("marimo-anywidget")
  .withData(
    z.object({
      jsUrl: z.string(),
      css: z.string().nullish(),
    }),
  )
  .withFunctions<PluginFunctions>({
    send_to_widget: rpc
      .input(z.object({ content: z.any() }))
      .output(z.null().optional()),
  })
  .renderer((props) => <AnyWidgetSlot {...props} />);

type Props = IPluginProps<T, Data, PluginFunctions>;

const AnyWidgetSlot = (props: Props) => {
  const { css, jsUrl } = props.data;
  // JS is an ESM file with a render function on it
  // export function render({ model, el }) {
  //   ...
  const {
    data: module,
    loading,
    error,
  } = useAsyncData(async () => {
    const baseUrl = document.baseURI;
    const url = new URL(jsUrl, baseUrl).toString();
    return await import(/* @vite-ignore */ url);
  }, []);

  // Mount the CSS
  useEffect(() => {
    if (!css || !props.host.shadowRoot) {
      return;
    }
    const style = document.createElement("style");
    style.innerHTML = css;
    props.host.shadowRoot.append(style);
    return () => {
      style.remove();
    };
  }, [css, props.host]);

  if (error) {
    return <ErrorBanner error={error} />;
  }

  if (!module || loading) {
    return null;
  }

  if (!isAnyWidgetModule(module)) {
    const error = new Error(
      `Module at ${jsUrl} does not appear to be a valid anywidget`,
    );
    return <ErrorBanner error={error} />;
  }

  return <LoadedSlot {...props} widget={module.default} />;
};

/**
 * Run the anywidget module
 *
 * @param widgetDef - The anywidget definition
 * @param model - The model to pass to the widget
 */
async function runAnyWidgetModule(widgetDef: AnyWidget, model: Model<T>, el: HTMLElement) {
  const widget = typeof widgetDef === "function" ? await widgetDef() : widgetDef;
  await widget.initialize?.({ model });
  await widget.render?.({ model, el });
}

function isAnyWidgetModule(mod: any): mod is { default: AnyWidget } {
  return (
    mod.default &&
    (typeof mod.default === "function" ||
      mod.default?.render ||
      mod.default?.initialize)
  );
}

const LoadedSlot = ({
  value,
  setValue,
  widget,
  functions,
  host,
}: Props & { widget: AnyWidget }) => {
  const ref = useRef<HTMLDivElement>(null);
  const model = useRef<Model<T>>(
    new Model(value, setValue, functions.send_to_widget),
  );

  // Listen to incoming messages
  useEventListener(host, MarimoIncomingMessageEvent.TYPE, (e) => {
    model.current.receiveCustomMessage(e.detail.message, e.detail.buffers);
  });

  useOnMount(() => {
    if (!ref.current) {
      return;
    }
    runAnyWidgetModule(widget, model.current, ref.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  });

  // When the value changes, update the model
  useEffect(() => {
    model.current.updateAndEmitDiffs(value);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [useDeepCompareMemoize([value])]);

  return <div ref={ref} />;
};

class Model<T extends Record<string, any>> implements AnyModel<T> {
  constructor(
    private data: T,
    private onChange: (value: T) => void,
    private send_to_widget: (req: { content?: any }) => Promise<
      null | undefined
    >,
  ) { }

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
    this.send_to_widget({ content }).then(callbacks);
  }

  widget_manager = new Proxy(
    {},
    {
      get() {
        throw new Error("widget_manager not supported in marimo");
      },
      set() {
        throw new Error("widget_manager not supported in marimo");
      },
    },
  );

  private listeners: Record<string, Set<EventHandler>> = {};

  get<K extends keyof T>(key: K): T[K] {
    return this.data[key];
  }

  set<K extends keyof T>(key: K, value: T[K]): void {
    this.data = { ...this.data, [key]: value };
    this.emit(`change:${key as K & string}`, value);
  }

  save_changes(): void {
    this.onChange(this.data);
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
    this.listeners["msg:custom"]?.forEach((cb) => cb(message, buffers));
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
}
