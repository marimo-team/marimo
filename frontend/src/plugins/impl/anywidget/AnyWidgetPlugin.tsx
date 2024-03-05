/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { z } from "zod";

import { IPlugin, IPluginProps } from "@/plugins/types";
import { useEffect, useRef } from "react";
import { useAsyncData } from "@/hooks/useAsyncData";
import { dequal } from "dequal";
import { useOnMount } from "@/hooks/useLifecycle";
import { useDeepCompareMemoize } from "@/hooks/useDeepCompareMemoize";
import { ErrorBanner } from "../common/error-banner";

interface Data {
  jsUrl: string;
  css?: string | null;
}

type T = Record<string, any>;

export class AnyWidgetPlugin implements IPlugin<T, Data> {
  tagName = "marimo-anywidget";

  validator = z.object({
    jsUrl: z.string(),
    css: z.string().nullish(),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    return <AnyWidgetSlot {...props} />;
  }
}

const AnyWidgetSlot = (props: IPluginProps<T, Data>) => {
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
    return await import(url);
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

  if (!module.default.render) {
    const error = new Error(
      `Module at ${jsUrl} does not have a default export with a render function`,
    );
    return <ErrorBanner error={error} />;
  }

  return <LoadedSlot {...props} render={module.default.render} />;
};

const LoadedSlot = ({
  value,
  setValue,
  render,
}: IPluginProps<T, Data> & {
  render: ({ model, el }: any) => void;
}) => {
  const ref = useRef<HTMLDivElement>(null);
  const model = useRef<Model<T>>(new Model(value, setValue));

  useOnMount(() => {
    if (!ref.current) {
      return;
    }

    render({ model: model.current, el: ref.current });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  });

  // When the value changes, update the model
  useEffect(() => {
    model.current.updateAndEmitDiffs(value);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [useDeepCompareMemoize([value])]);

  return <div ref={ref} />;
};

class Model<T extends Record<string, any>> {
  constructor(
    public data: T,
    public onChange: (value: T) => void,
  ) {}

  private listeners: Record<string, Array<(value: any) => void>> = {};

  public get<K extends keyof T>(key: K): T[K] {
    return this.data[key];
  }

  public set<K extends keyof T>(key: K, value: T[K]): void {
    this.data = { ...this.data, [key]: value };
    this.emit(`change:${key as K & string}`, value);
  }

  public save_changes(): void {
    this.onChange(this.data);
  }

  public updateAndEmitDiffs(value: T): void {
    Object.keys(value).forEach((key) => {
      const k = key as keyof T;
      if (!dequal(this.data[k], value[k])) {
        this.set(k, value[k]);
      }
    });
  }

  public on<K extends keyof T>(
    event: `change:${K & string}`,
    callback: (value: T[K]) => void,
  ): void {
    if (!this.listeners[event]) {
      this.listeners[event] = [];
    }
    this.listeners[event].push(callback);
  }

  private emit<K extends keyof T>(event: `change:${K & string}`, value: T[K]) {
    if (!this.listeners[event]) {
      return;
    }
    this.listeners[event].forEach((cb) => cb(value));
  }
}
