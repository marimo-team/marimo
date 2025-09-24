/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */

import type { AnyWidget, Experimental } from "@anywidget/types";
import { get, isEqual, set } from "lodash-es";
import { useEffect, useMemo, useRef } from "react";
import { z } from "zod";
import { MarimoIncomingMessageEvent } from "@/core/dom/events";
import { asRemoteURL } from "@/core/runtime/config";
import { useAsyncData } from "@/hooks/useAsyncData";
import { useDeepCompareMemoize } from "@/hooks/useDeepCompareMemoize";
import {
  type HTMLElementNotDerivedFromRef,
  useEventListener,
} from "@/hooks/useEventListener";
import { createPlugin } from "@/plugins/core/builder";
import { rpc } from "@/plugins/core/rpc";
import type { IPluginProps } from "@/plugins/types";
import {
  type Base64String,
  byteStringToBinary,
  typedAtob,
} from "@/utils/json/base64";
import { Logger } from "@/utils/Logger";
import { ErrorBanner } from "../common/error-banner";
import { MODEL_MANAGER, Model } from "./model";

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

  const valueWithBuffers = useMemo(() => {
    return resolveInitialValue(props.value, bufferPaths ?? []);
  }, [props.value, bufferPaths]);

  // JS is an ESM file with a render function on it
  // export function render({ model, el }) {
  //   ...
  const {
    data: module,
    error,
    refetch,
  } = useAsyncData(async () => {
    const url = asRemoteURL(jsUrl).toString();
    return await import(/* @vite-ignore */ url);
    // Re-render on jsHash change (which is a hash of the contents of the file)
    // instead of a jsUrl change because URLs may change without the contents
    // actually changing (and we don't want to re-render on every change).
    // If there is an error loading the URL (e.g. maybe an invalid or old URL),
    // we also want to re-render.
  }, [jsHash]);

  // If there is an error and the jsUrl has changed, we want to re-render
  // because the URL may have changed to a valid URL.
  const hasError = Boolean(error);
  useEffect(() => {
    if (hasError && jsUrl) {
      refetch();
    }
  }, [hasError, jsUrl]);

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
      value={valueWithBuffers}
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

export function resolveInitialValue(
  raw: Record<string, any>,
  bufferPaths: ReadonlyArray<ReadonlyArray<string | number>>,
) {
  const out = structuredClone(raw);
  for (const bufferPath of bufferPaths) {
    const base64String: Base64String = get(raw, bufferPath);
    const bytes = byteStringToBinary(typedAtob(base64String));
    set(out, bufferPath, new DataView(bytes.buffer));
  }
  return out;
}
