/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { z } from "zod";

import type { IPluginProps } from "@/plugins/types";
import { useEffect, useMemo, useRef } from "react";
import { useAsyncData } from "@/hooks/useAsyncData";
import { useDeepCompareMemoize } from "@/hooks/useDeepCompareMemoize";
import { ErrorBanner } from "../common/error-banner";
import { createPlugin } from "@/plugins/core/builder";
import { rpc } from "@/plugins/core/rpc";
import type { AnyWidget, Experimental } from "@anywidget/types";
import { Logger } from "@/utils/Logger";
import {
  type HTMLElementNotDerivedFromRef,
  useEventListener,
} from "@/hooks/useEventListener";
import { MarimoIncomingMessageEvent } from "@/core/dom/events";
import { updateBufferPaths } from "@/utils/data-views";
import { Model } from "./model";

interface Data {
  jsUrl: string;
  jsHash: string;
  css?: string | null;
  bufferPaths?: Array<Array<string | number>> | null;
}

type T = Record<string, any>;

// eslint-disable-next-line @typescript-eslint/consistent-type-definitions
type PluginFunctions = {
  send_to_widget: <T>(req: { content?: any }) => Promise<null | undefined>;
};

export const AnyWidgetPlugin = createPlugin<T>("marimo-anywidget")
  .withData(
    z.object({
      jsUrl: z.string(),
      jsHash: z.string(),
      css: z.string().nullish(),
      bufferPaths: z
        .array(z.array(z.union([z.string(), z.number()])))
        .nullish(),
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
  const { css, jsUrl, jsHash, bufferPaths } = props.data;
  // JS is an ESM file with a render function on it
  // export function render({ model, el }) {
  //   ...
  const { data: module, error } = useAsyncData(async () => {
    const baseUrl = document.baseURI;
    const url = new URL(jsUrl, baseUrl).toString();
    return await import(/* @vite-ignore */ url);
    // Re-render on jsHash change instead of url change (since URLs may change)
  }, [jsHash]);

  const valueWithBuffer = useMemo(() => {
    return updateBufferPaths(props.value, bufferPaths);
  }, [props.value, bufferPaths]);

  // Mount the CSS
  useEffect(() => {
    const shadowRoot = props.host.shadowRoot;
    if (!css || !shadowRoot) {
      return;
    }

    // Try constructed stylesheets first
    if (
      "adoptedStyleSheets" in Document.prototype &&
      "replace" in CSSStyleSheet.prototype
    ) {
      const sheet = new CSSStyleSheet();
      try {
        sheet.replaceSync(css);
        if (shadowRoot) {
          shadowRoot.adoptedStyleSheets = [
            ...shadowRoot.adoptedStyleSheets,
            sheet,
          ];
        }
        return () => {
          if (shadowRoot) {
            shadowRoot.adoptedStyleSheets =
              shadowRoot.adoptedStyleSheets.filter((s) => s !== sheet);
          }
        };
      } catch {
        // Fall through to inline styles if constructed sheets fail
      }
    }

    // Fallback to inline styles
    const style = document.createElement("style");
    style.innerHTML = css;
    shadowRoot.append(style);
    return () => {
      style.remove();
    };
  }, [css, props.host]);

  if (error) {
    return <ErrorBanner error={error} />;
  }

  if (!module) {
    return null;
  }

  if (!isAnyWidgetModule(module)) {
    const error = new Error(
      `Module at ${jsUrl} does not appear to be a valid anywidget`,
    );
    return <ErrorBanner error={error} />;
  }

  return (
    <LoadedSlot {...props} widget={module.default} value={valueWithBuffer} />
  );
};

/**
 * Run the anywidget module
 *
 * @param widgetDef - The anywidget definition
 * @param model - The model to pass to the widget
 */
async function runAnyWidgetModule(
  widgetDef: AnyWidget,
  model: Model<T>,
  el: HTMLElement,
) {
  const experimental: Experimental = {
    invoke: async (name, msg, options) => {
      const message =
        "anywidget.invoke not supported in marimo. Please file an issue at https://github.com/marimo-team/marimo/issues";
      Logger.warn(message);
      throw new Error(message);
    },
  };
  // Clear the element, in case the widget is re-rendering
  el.innerHTML = "";
  const widget =
    typeof widgetDef === "function" ? await widgetDef() : widgetDef;
  await widget.initialize?.({ model, experimental });
  await widget.render?.({ model, el, experimental });
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
  useEventListener(
    host as HTMLElementNotDerivedFromRef,
    MarimoIncomingMessageEvent.TYPE,
    (e) => {
      model.current.receiveCustomMessage(e.detail.message, e.detail.buffers);
    },
  );

  useEffect(() => {
    if (!ref.current) {
      return;
    }
    runAnyWidgetModule(widget, model.current, ref.current);
  }, [widget]);

  // When the value changes, update the model
  const valueMemo = useDeepCompareMemoize(value);
  useEffect(() => {
    model.current.updateAndEmitDiffs(valueMemo);
  }, [valueMemo]);

  return <div ref={ref} />;
};
