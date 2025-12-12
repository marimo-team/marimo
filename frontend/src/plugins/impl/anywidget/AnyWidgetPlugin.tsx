/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */

import type { AnyWidget, Experimental } from "@anywidget/types";
import { isEqual } from "lodash-es";
import { useEffect, useMemo, useRef } from "react";
import useEvent from "react-use-event-hook";
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
  decodeFromWire,
  isWireFormat,
  serializeBuffersToBase64,
  type WireFormat,
} from "@/utils/data-views";
import { prettyError } from "@/utils/errors";
import type { Base64String } from "@/utils/json/base64";
import { Logger } from "@/utils/Logger";
import { ErrorBanner } from "../common/error-banner";
import { MODEL_MANAGER, Model } from "./model";

interface Data {
  jsUrl: string;
  jsHash: string;
  css?: string | null;
}

type T = Record<string, unknown>;

// eslint-disable-next-line @typescript-eslint/consistent-type-definitions
type PluginFunctions = {
  send_to_widget: <T>(req: {
    content: unknown;
    buffers: Base64String[];
  }) => Promise<null | undefined>;
};

export const AnyWidgetPlugin = createPlugin<WireFormat<T>>("marimo-anywidget")
  .withData(
    z.object({
      jsUrl: z.string(),
      jsHash: z.string(),
      css: z.string().nullish(),
    }),
  )
  .withFunctions<PluginFunctions>({
    send_to_widget: rpc
      .input(
        z.object({
          content: z.unknown(),
          buffers: z.array(z.string().transform((v) => v as Base64String)),
        }),
      )
      .output(z.null().optional()),
  })
  .renderer((props) => <AnyWidgetSlot {...props} />);

const AnyWidgetSlot = (
  props: IPluginProps<WireFormat<T>, Data, PluginFunctions>,
) => {
  const { css, jsUrl, jsHash } = props.data;

  // Decode wire format { state, bufferPaths, buffers } to state with DataViews
  const valueWithBuffers = useMemo(() => {
    if (isWireFormat(props.value)) {
      const decoded = decodeFromWire(props.value);
      Logger.debug("AnyWidget decoded wire format:", {
        bufferPaths: props.value.bufferPaths,
        buffersCount: props.value.buffers?.length,
        decodedKeys: Object.keys(decoded),
      });
      return decoded;
    }
    Logger.warn("AnyWidget value is not wire format:", props.value);
    return props.value;
  }, [props.value]);

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

  // Wrap setValue to serialize DataViews back to base64 before sending
  // Structure matches ipywidgets protocol: { state, bufferPaths, buffers }
  const wrappedSetValue = useEvent((partialValue: Partial<T>) =>
    props.setValue(serializeBuffersToBase64(partialValue)),
  );

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
      setValue={wrappedSetValue}
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
    invoke: async (_name, _msg, _options) => {
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
  try {
    const unsub = await widget.render?.({ model, el, experimental });
    return () => {
      unsub?.();
    };
  } catch (error) {
    Logger.error("Error rendering anywidget", error);
    el.classList.add("text-error");
    el.innerHTML = `Error rendering anywidget: ${prettyError(error)}`;
    return () => {
      // No-op
    };
  }
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

interface Props
  extends Omit<IPluginProps<T, Data, PluginFunctions>, "setValue"> {
  widget: AnyWidget;
  value: T;
  setValue: (value: Partial<T>) => void;
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

  // value is already decoded from wire format
  const model = useRef<Model<T>>(
    new Model(value, setValue, functions.send_to_widget, new Set()),
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
