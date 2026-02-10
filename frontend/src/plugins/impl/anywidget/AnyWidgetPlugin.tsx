/* Copyright 2026 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */

import type { AnyWidget } from "@anywidget/types";
import { useEffect, useRef } from "react";
import { z } from "zod";
import { useAsyncData } from "@/hooks/useAsyncData";
import type { HTMLElementNotDerivedFromRef } from "@/hooks/useEventListener";
import { createPlugin } from "@/plugins/core/builder";
import type { IPluginProps } from "@/plugins/types";
import { prettyError } from "@/utils/errors";
import { Logger } from "@/utils/Logger";
import { ErrorBanner } from "../common/error-banner";
import { MODEL_MANAGER, type Model } from "./model";
import type { ModelState, WidgetModelId } from "./types";
import { BINDING_MANAGER, WIDGET_DEF_REGISTRY } from "./widget-binding";

/**
 * AnyWidget asset data
 */
interface Data {
  jsUrl: string;
  jsHash: string;
}

type AnyWidgetState = ModelState;

/**
 * Initial value is a model_id reference.
 * The backend sends just { model_id: string } and the frontend
 * retrieves the actual state from the 'open' message.
 */
interface ModelIdRef {
  model_id: WidgetModelId;
}

export function useAnyWidgetModule(opts: { jsUrl: string; jsHash: string }) {
  const { jsUrl, jsHash } = opts;

  // JS is an ESM file with a render function on it
  // export function render({ model, el }) {
  //   ...
  const {
    data: jsModule,
    error,
    refetch,
  } = useAsyncData(async () => {
    return await WIDGET_DEF_REGISTRY.getModule(jsUrl, jsHash);
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
      WIDGET_DEF_REGISTRY.invalidate(jsHash);
      refetch();
    }
  }, [hasError, jsUrl]);

  return {
    jsModule,
    error,
  };
}

export function useMountCss(css: string | null | undefined, host: HTMLElement) {
  // Mount the CSS
  useEffect(() => {
    const shadowRoot = host.shadowRoot;
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
  }, [css, host]);
}

export const AnyWidgetPlugin = createPlugin<ModelIdRef>("marimo-anywidget")
  .withData(
    z.object({
      jsUrl: z.string(),
      jsHash: z.string(),
    }),
  )
  .withFunctions({})
  .renderer((props) => <AnyWidgetSlot {...props} />);

const AnyWidgetSlot = (props: IPluginProps<ModelIdRef, Data>) => {
  const { jsUrl, jsHash } = props.data;
  const { model_id: modelId } = props.value;
  const host = props.host as HTMLElementNotDerivedFromRef;

  const { jsModule, error } = useAnyWidgetModule({ jsUrl, jsHash });

  if (error) {
    return <ErrorBanner error={error} />;
  }

  if (!jsModule) {
    return null;
  }

  if (!isAnyWidgetModule(jsModule)) {
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
      widget={jsModule.default}
      modelId={modelId}
      host={host}
    />
  );
};

/**
 * Run the anywidget module
 *
 * Per AFM spec (anywidget.dev/en/afm):
 * - initialize() is called once per model lifetime
 * - render() is called once per view (can be multiple per model)
 */
async function runAnyWidgetModule<T extends AnyWidgetState>(
  widgetDef: AnyWidget<T>,
  model: Model<T>,
  modelId: WidgetModelId,
  el: HTMLElement,
  signal: AbortSignal,
): Promise<void> {
  // Clear the element, in case the widget is re-rendering
  el.innerHTML = "";

  try {
    const binding = BINDING_MANAGER.getOrCreate(modelId);
    const render = await binding.bind(widgetDef, model);
    await render(el, signal);
  } catch (error) {
    Logger.error("Error rendering anywidget", error);
    el.classList.add("text-error");
    el.innerHTML = `Error rendering anywidget: ${prettyError(error)}`;
  }
}

function isAnyWidgetModule(mod: any): mod is { default: AnyWidget } {
  if (!mod.default) {
    return false;
  }

  return (
    typeof mod.default === "function" ||
    typeof mod.default?.render === "function" ||
    typeof mod.default?.initialize === "function"
  );
}

interface Props<T extends AnyWidgetState> {
  widget: AnyWidget<T>;
  modelId: WidgetModelId;
  host: HTMLElementNotDerivedFromRef;
}

const LoadedSlot = <T extends AnyWidgetState>({
  widget,
  modelId,
  host,
}: Props<T> & { widget: AnyWidget<T> }) => {
  const htmlRef = useRef<HTMLDivElement>(null);

  // value is already decoded from wire format, may be null if waiting for open message
  const model = MODEL_MANAGER.getSync(modelId);

  if (!model) {
    Logger.error("Model not found for modelId", modelId);
  }

  const css = model?.get("_css");
  useMountCss(css, host);

  useEffect(() => {
    if (!htmlRef.current || !model) {
      return;
    }
    const controller = new AbortController();
    runAnyWidgetModule(
      widget,
      model,
      modelId,
      htmlRef.current,
      controller.signal,
    );
    return () => controller.abort();
    // We re-run the widget when the modelId changes, which means the cell
    // that created the Widget has been re-run.
    // We need to re-run the widget because it may contain initialization code
    // that could be reset by the new widget.
    // See example: https://github.com/marimo-team/marimo/issues/3962#issuecomment-2703184123
  }, [widget, modelId, model]);

  return <div ref={htmlRef} />;
};

export const visibleForTesting = {
  LoadedSlot,
  runAnyWidgetModule,
  isAnyWidgetModule,
};
