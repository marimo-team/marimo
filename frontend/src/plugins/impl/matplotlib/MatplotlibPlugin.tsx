/* Copyright 2026 Marimo. All rights reserved. */

import { type JSX, useEffect, useRef } from "react";
import { z } from "zod";
import type { IPlugin, IPluginProps } from "@/plugins/types";
import {
  type Data,
  MatplotlibRenderer,
  type MatplotlibState,
  type SelectionValue as T,
} from "./matplotlib-renderer";

export class MatplotlibPlugin implements IPlugin<T, Data> {
  tagName = "marimo-matplotlib";

  validator = z.object({
    chartBase64: z.string(),
    xBounds: z.tuple([z.number(), z.number()]),
    yBounds: z.tuple([z.number(), z.number()]),
    axesPixelBounds: z.tuple([z.number(), z.number(), z.number(), z.number()]),
    width: z.number(),
    height: z.number(),
    selectionColor: z.string().default("#3b82f6"),
    selectionOpacity: z.number().default(0.15),
    strokeWidth: z.number().default(2),
    debounce: z.boolean(),
    xScale: z.enum(["linear", "log"]).default("linear"),
    yScale: z.enum(["linear", "log"]).default("linear"),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    return (
      <MatplotlibComponent
        {...props.data}
        value={props.value}
        setValue={props.setValue}
      />
    );
  }
}

const MatplotlibComponent = (props: MatplotlibState) => {
  const ref = useRef<HTMLDivElement>(null);
  const instance = useRef<MatplotlibRenderer | null>(null);

  useEffect(() => {
    const container = ref.current;
    if (!container) {
      return;
    }
    const controller = new AbortController();
    instance.current = new MatplotlibRenderer(container, {
      state: props,
      signal: controller.signal,
    });
    return () => {
      controller.abort();
      instance.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // No dependency array: intentionally syncs all props into the imperative
  // renderer after every render. The renderer's update() method diffs internally.
  useEffect(() => {
    instance.current?.update(props);
  });

  return <div ref={ref} />;
};
