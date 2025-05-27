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
import { Model, MODEL_MANAGER } from "./model";
import { isEqual } from "lodash-es";

interface Data {
  jsUrl: string;
  jsHash: string;
  css?: string | null;
  bufferPaths?: Array<Array<string | number>> | null;
  initialValue: T;
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
      initialValue: z.object({}).passthrough(),
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

  // Find the closest parent element with an attribute of `random-id`
  const randomId = props.host.closest("[random-id]")?.getAttribute("random-id");
  const key = randomId ?? jsUrl;

  return (
    <LoadedSlot
      // Use the a key to force a re-render when the randomId (or jsUrl) changes
      // Plugins may be stateful and we cannot make assumptions that we won't be
      // so it is safer to just re-render.
      key={key}
      {...props}
      widget={module.default}
      value={valueWithBuffer}
    />
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
): Promise<() => void> {
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
  const unsub = await widget.render?.({ model, el, experimental });
  return () => {
    unsub?.();
  };
}

function isAnyWidgetModule(mod: any): mod is { default: AnyWidget } {
  return (
    mod.default &&
    (typeof mod.default === "function" ||
      mod.default?.render ||
      mod.default?.initialize)
  );
}

export function getDirtyFields(value: T, initialValue: T): Set<keyof T> {
  return new Set(
    Object.keys(value).filter((key) => !isEqual(value[key], initialValue[key])),
  );
}

function hasModelId(message: unknown): message is { model_id: string } {
  return (
    typeof message === "object" && message !== null && "model_id" in message
  );
}

const LoadedSlot = ({
  value,
  setValue,
  widget,
  functions,
  data,
  host,
}: Props & { widget: AnyWidget }) => {
  const htmlRef = useRef<HTMLDivElement>(null);

  const model = useRef<Model<T>>(
    new Model(
      // Merge the initial value with the current value
      // since we only send partial updates to the backend
      { ...data.initialValue, ...value },
      setValue,
      functions.send_to_widget,
      getDirtyFields(value, data.initialValue),
    ),
  );

  // Listen to incoming messages
  useEventListener(
    host as HTMLElementNotDerivedFromRef,
    MarimoIncomingMessageEvent.TYPE,
    (e) => {
      const message = e.detail.message;
      if (hasModelId(message)) {
        MODEL_MANAGER.get(message.model_id).then((model) => {
          model.receiveCustomMessage(message, e.detail.buffers);
        });
      } else {
        model.current.receiveCustomMessage(message, e.detail.buffers);
      }
    },
  );

  useEffect(() => {
    if (!htmlRef.current) {
      return;
    }
    const unsubPromise = runAnyWidgetModule(
      widget,
      model.current,
      htmlRef.current,
    );
    return () => {
      unsubPromise.then((unsub) => unsub());
    };
    // We re-run the widget when the jsUrl changes, which means the cell
    // that created the Widget has been re-run.
    // We need to re-run the widget because it may contain initialization code
    // that could be reset by the new widget.
    // See example: https://github.com/marimo-team/marimo/issues/3962#issuecomment-2703184123
  }, [widget, data.jsUrl]);

  // When the value changes, update the model
  const valueMemo = useDeepCompareMemoize(value);
  useEffect(() => {
    model.current.updateAndEmitDiffs(valueMemo);
  }, [valueMemo]);

  return <div ref={htmlRef} />;
};

export const visibleForTesting = {
  LoadedSlot,
  runAnyWidgetModule,
  isAnyWidgetModule,
  getDirtyFields,
};
