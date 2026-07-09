/* Copyright 2026 Marimo. All rights reserved. */

import { useEffect, useRef, useState } from "react";
import { z } from "zod";
import { useAsyncData } from "@/hooks/useAsyncData";
import type { HTMLElementNotDerivedFromRef } from "@/hooks/useEventListener";
import { createPlugin } from "@/plugins/core/builder";
import type { IPluginProps } from "@/plugins/types";
import { prettyError } from "@/utils/errors";
import { Logger } from "@/utils/Logger";
import { ErrorBanner } from "../common/error-banner";
import type { Model } from "./model";
import { WIDGET_REGISTRY } from "./registry";
import type { ModelState, WidgetModelId } from "./types";
import type { WidgetBinding } from "./widget-binding";

/**
 * The component's only data attribute; everything else arrives through
 * the model's comm messages, keyed by this id.
 */
interface Data {
  modelId: WidgetModelId;
}

type AnyWidgetState = ModelState;

/**
 * Value payload sent by the frontend on state updates.
 *
 * The initial value from the backend is empty — `model_id` is passed
 * via immutable data attributes (`args`) so it survives value overwrites.
 */
interface ModelIdRef {
  model_id?: WidgetModelId;
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
      modelId: z.string().transform((v) => v as WidgetModelId),
    }),
  )
  .withFunctions({})
  .renderer((props) => <AnyWidgetSlot {...props} />);

/**
 * The registry resolves the model, imports the widget's code, and runs
 * `initialize`; this component's job is views — and remounting when
 * `modelId` changes, which is what a cell re-run produces (#3962).
 */
const AnyWidgetSlot = (props: IPluginProps<ModelIdRef, Data>) => {
  const { modelId } = props.data;
  const host = props.host as HTMLElementNotDerivedFromRef;

  const { data, error } = useAsyncData(async () => {
    const widget = await WIDGET_REGISTRY.getWidget(modelId);
    // Tag the result with the id it was loaded for so the old view
    // stays mounted until the new widget is ready (useAsyncData exposes
    // the previous result during a cell re-run transition).
    return { modelId, ...widget };
  }, [modelId]);

  if (error) {
    return <ErrorBanner error={error} />;
  }

  if (!data) {
    return null;
  }

  return (
    <LoadedSlot
      // Remount when the model changes (cell re-run: new comm, new id);
      // value updates leave the key stable.
      key={data.modelId}
      model={data.model}
      binding={data.binding}
      host={host}
    />
  );
};

interface LoadedSlotProps {
  model: Model<AnyWidgetState>;
  binding: WidgetBinding<AnyWidgetState>;
  host: HTMLElementNotDerivedFromRef;
}

/**
 * One mounted view of an initialized widget (render runs once per
 * view; the registry already ran initialize).
 */
const LoadedSlot = ({ model, binding, host }: LoadedSlotProps) => {
  const htmlRef = useRef<HTMLDivElement>(null);

  // CSS is state, not code, so it hot-applies in every mode.
  const [css, setCss] = useState<string | null | undefined>(() =>
    model.get("_css"),
  );
  useEffect(() => {
    const controller = new AbortController();
    model.on("change:_css", (value: string) => setCss(value), {
      signal: controller.signal,
    });
    return () => controller.abort();
  }, [model]);
  useMountCss(css, host);

  useEffect(() => {
    const el = htmlRef.current;
    if (!el) {
      return;
    }
    const controller = new AbortController();
    binding.createView({ el }, { signal: controller.signal }).catch((error) => {
      Logger.error("Error rendering anywidget", error);
      el.classList.add("text-error");
      el.innerHTML = `Error rendering anywidget: ${prettyError(error)}`;
    });
    return () => controller.abort();
  }, [binding, model]);

  return <div ref={htmlRef} />;
};

export const visibleForTesting = {
  AnyWidgetSlot,
  LoadedSlot,
};
