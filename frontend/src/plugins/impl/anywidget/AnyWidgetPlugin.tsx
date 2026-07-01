/* Copyright 2026 Marimo. All rights reserved. */
/* oxlint-disable typescript/no-explicit-any */

import type { AnyWidget } from "@anywidget/types";
import { useEffect, useRef } from "react";
import { z } from "zod";
import { useAsyncData } from "@/hooks/useAsyncData";
import type { HTMLElementNotDerivedFromRef } from "@/hooks/useEventListener";
import { createPlugin } from "@/plugins/core/builder";
import type { IPluginProps } from "@/plugins/types";
import { prettyError } from "@/utils/errors";
import { Logger } from "@/utils/Logger";
import { hasFunctionProperty, isRecord } from "@/utils/records";
import { ErrorBanner } from "../common/error-banner";
import { getMarimoInternal, MODEL_MANAGER, type Model } from "./model";
import type { ModelState, WidgetModelId } from "./types";
import { BINDING_MANAGER, WIDGET_DEF_REGISTRY } from "./widget-binding";

/**
 * AnyWidget asset data
 */
interface Data {
  jsUrl: string;
  jsHash: string;
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
      modelId: z.string().transform((v) => v as WidgetModelId),
    }),
  )
  .withFunctions({})
  .renderer((props) => <AnyWidgetSlot {...props} />);

const AnyWidgetSlot = (props: IPluginProps<ModelIdRef, Data>) => {
  const { jsUrl, jsHash, modelId } = props.data;
  const host = props.host as HTMLElementNotDerivedFromRef;

  const { jsModule, error } = useAnyWidgetModule({ jsUrl, jsHash });

  if (error) {
    return <ErrorBanner error={error} />;
  }

  if (!jsModule) {
    return null;
  }

  const widget = resolveAnyWidget(jsModule, jsUrl);
  if (!widget) {
    return (
      <ErrorBanner error={getInvalidAnyWidgetModuleError(jsModule, jsUrl)} />
    );
  }

  return (
    <LoadedSlot
      // Force remount when the widget module or model changes (cell re-run).
      key={`${jsHash}:${modelId}`}
      widget={widget}
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
    // Replay current model values so render listeners observe hydrated state
    // even if backend updates arrived before listeners were attached.
    getMarimoInternal(model).reemitState();
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

const warnedLegacyNamedExportUrls = new Set<string>();

/**
 * Resolve the {@link AnyWidget} from a loaded ES module.
 *
 * Prefers the AFM-spec default export. Falls back to legacy top-level named
 * `render`/`initialize` exports — which anywidget's own runtime still supports
 * (with a deprecation warning) — by synthesizing a widget object, so widgets
 * that render in Jupyter/Colab also render in marimo instead of being rejected.
 *
 * Returns `null` if the module is not a valid anywidget.
 */
function resolveAnyWidget(mod: any, jsUrl: string): AnyWidget | null {
  if (isAnyWidgetModule(mod)) {
    return mod.default;
  }

  // Legacy (pre-AFM): top-level named `render`/`initialize` exports.
  const hasNamedRender = typeof mod?.render === "function";
  const hasNamedInitialize = typeof mod?.initialize === "function";
  if (hasNamedRender || hasNamedInitialize) {
    if (!warnedLegacyNamedExportUrls.has(jsUrl)) {
      warnedLegacyNamedExportUrls.add(jsUrl);
      Logger.warn(
        `Anywidget module at ${jsUrl} uses deprecated top-level named ` +
          "exports (`render`/`initialize`). Per the AFM spec, use a default " +
          "export instead: `export default { render }`. " +
          "See https://anywidget.dev/en/afm/",
      );
    }
    return {
      render: mod.render,
      initialize: mod.initialize,
    };
  }

  return null;
}

function getInvalidAnyWidgetModuleError(mod: unknown, jsUrl: string): Error {
  const afmDocs = "https://anywidget.dev/en/afm/";
  const hasNamedRender = isRecord(mod) && hasFunctionProperty(mod, "render");
  const hasNamedInitialize =
    isRecord(mod) && hasFunctionProperty(mod, "initialize");

  if (hasNamedRender || hasNamedInitialize) {
    const namedExports = [
      hasNamedRender ? "`render`" : null,
      hasNamedInitialize ? "`initialize`" : null,
    ]
      .filter(Boolean)
      .join(" and ");
    const lifecycleHooks = [
      hasNamedRender ? "render" : null,
      hasNamedInitialize ? "initialize" : null,
    ].filter((hook): hook is string => hook !== null);
    const defaultExportExample = `export default { ${lifecycleHooks.join(", ")} }`;
    const namedExportExample =
      lifecycleHooks.length === 1
        ? `export function ${lifecycleHooks[0]}`
        : "named export function ...";
    return new Error(
      `Anywidget module at ${jsUrl} uses named exports (${namedExports}). ` +
        "Per the AFM spec, use a default export instead: " +
        `\`${defaultExportExample}\` (not \`${namedExportExample}\`). ` +
        `See ${afmDocs}`,
    );
  }

  if (!isRecord(mod) || mod.default === undefined) {
    return new Error(
      `Anywidget module at ${jsUrl} is missing a default export. ` +
        "Per the AFM spec, use `export default { render }` or " +
        "`export default async () => ({ render })`. " +
        `See ${afmDocs}`,
    );
  }

  return new Error(
    `Anywidget module at ${jsUrl} has an invalid default export. ` +
      "Expected a factory function or an object with `render` or `initialize`. " +
      `See ${afmDocs}`,
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
  resolveAnyWidget,
  getInvalidAnyWidgetModuleError,
};
