/* Copyright 2026 Marimo. All rights reserved. */

/* eslint-disable unicorn/prefer-spread */
/**
 * WebComponent Factory for React Components
 *
 * Provides a factory for defining a custom web component from a React
 * component. The factory handles the logic of communicating UI element values
 * to and from the rest of marimo.
 */
import { Provider } from "jotai";
import React, {
  createRef,
  type JSX,
  type ReactNode,
  type SetStateAction,
  Suspense,
  useEffect,
  useImperativeHandle,
  useMemo,
  useState,
} from "react";
import ReactDOM, { type Root } from "react-dom/client";
import useEvent from "react-use-event-hook";
import { type ZodSchema, z } from "zod";
import { notebookAtom } from "@/core/cells/cells.ts";
import { HTMLCellId } from "@/core/cells/ids.ts";
import { isUninstantiated } from "@/core/cells/utils";
import { createInputEvent, MarimoValueUpdateEvent } from "@/core/dom/events";
import { getUIElementObjectId } from "@/core/dom/ui-element";
import { UIElementRegistry } from "@/core/dom/uiregistry";
import { FUNCTIONS_REGISTRY } from "@/core/functions/FunctionRegistry";
import { LocaleProvider } from "@/core/i18n/locale-provider";
import { store } from "@/core/state/jotai";
import { isStaticNotebook } from "@/core/static/static-state";
import {
  type HTMLElementNotDerivedFromRef,
  useEventListener,
} from "@/hooks/useEventListener";
import { StyleNamespace } from "@/theme/namespace";
import { useTheme } from "@/theme/useTheme";
import { CellNotInitializedError } from "@/utils/errors.ts";
import { Functions } from "@/utils/functions";
import { shallowCompare } from "@/utils/shallow-compare";
import { defineCustomElement } from "../../core/dom/defineCustomElement";
import {
  parseAttrValue,
  parseDataset,
  parseInitialValue,
} from "../../core/dom/htmlUtils";
import { invariant } from "../../utils/invariant";
import { Logger } from "../../utils/Logger";
import { Objects } from "../../utils/objects";
import type { IPlugin } from "../types";
import { renderError } from "./BadPlugin";
import { renderHTML } from "./RenderHTML";
import type { PluginFunctions } from "./rpc";

export interface PluginSlotHandle {
  /**
   * Reset the plugin initial value and data.
   */
  reset: () => void;

  /**
   * Set the plugin's children.
   */
  setChildren: (children: ReactNode) => void;
}

export interface IMarimoHTMLElement extends HTMLElement {
  /**
   * Reset the plugin initial value and data.
   */
  reset: () => void;
  /**
   * Re-render the plugin.
   */
  rerender: () => void;
}

interface PluginSlotProps<T> {
  hostElement: HTMLElement;
  plugin: IPlugin<T, unknown>;
  children?: ReactNode | undefined;
  getInitialValue: () => T;
}

/* Handles synchronization of value on behalf of the component */

// eslint-disable-next-line react/function-component-definition
function PluginSlotInternal<T>(
  { hostElement, plugin, children, getInitialValue }: PluginSlotProps<T>,
  ref: React.Ref<PluginSlotHandle>,
): JSX.Element {
  const [childNodes, setChildNodes] = useState<ReactNode>(children);
  const [value, setValue] = useState<T>(getInitialValue());
  const { theme } = useTheme();

  const [parsedResult, setParsedResult] = useState(() => {
    return plugin.validator.safeParse(parseDataset(hostElement));
  });

  // Incremented on each reset to invalidate memoized function references.
  // This ensures that plugin functions (e.g., search) are re-created when
  // the underlying UI element instance changes (new object-id), even if
  // the element's data attributes haven't changed.
  const [resetNonce, setResetNonce] = useState(0);

  useImperativeHandle(ref, () => ({
    reset: () => {
      setValue(getInitialValue());
      setParsedResult(plugin.validator.safeParse(parseDataset(hostElement)));
      setResetNonce((n) => n + 1);
    },
    setChildren: (children) => {
      setChildNodes(children);
    },
  }));

  // Listen to value updates
  useEventListener(
    hostElement as HTMLElementNotDerivedFromRef,
    MarimoValueUpdateEvent.TYPE,
    (e) => {
      if (e.detail.element === hostElement) {
        setValue(e.detail.value as T);
      }
    },
  );

  // We create a mutation observer to listen for changes to the host element's attributes
  // and update the plugin's data accordingly
  useEffect(() => {
    const observer = new MutationObserver((mutations) => {
      const hasAttributeMutation = mutations.some(
        (mutation) =>
          mutation.type === "attributes" &&
          mutation.attributeName?.startsWith("data-"),
      );
      if (hasAttributeMutation) {
        setParsedResult(plugin.validator.safeParse(parseDataset(hostElement)));
      }
    });

    // Create listener
    observer.observe(hostElement, {
      attributes: true, // configure it to listen to attribute changes
    });

    return () => {
      // Remove listener
      observer.disconnect();
    };
  }, [hostElement, plugin.validator]);

  // When the value changes, send an input event
  const setValueAndSendInput = useEvent((value: SetStateAction<T>): void => {
    setValue((prevValue) => {
      const updater = Functions.asUpdater(value);
      const nextValue = updater(prevValue);
      // Shallow compare the values
      // If the value hasn't changed, we don't need to send an input event
      if (shallowCompare(nextValue, prevValue)) {
        return nextValue;
      }

      hostElement.dispatchEvent(createInputEvent(nextValue, hostElement));
      return nextValue;
    });
  });

  // Create a map of functions that can be called by the plugin
  const functionMethods = useMemo<PluginFunctions>(() => {
    if (!plugin.functions) {
      return {};
    }

    const methods: PluginFunctions = {};
    for (const [key, schemas] of Objects.entries(plugin.functions)) {
      const { input, output } = schemas as {
        input: ZodSchema<Record<string, unknown>>;
        output: ZodSchema<Record<string, unknown>>;
      };
      methods[key] = async (...args: unknown[]) => {
        invariant(
          args.length <= 1,
          `Plugin functions only supports a single argument. Called ${key}`,
        );
        const objectId = getUIElementObjectId(hostElement);
        invariant(objectId, "Object ID should exist");

        const isStatic = isStaticNotebook();

        const htmlId = HTMLCellId.findElementThroughShadowDOMs(hostElement)?.id;
        const cellId = htmlId ? HTMLCellId.parse(htmlId) : null;
        if (cellId && !isStatic) {
          // If the cell is not initialized, throw an error
          // Continue if the cell is static, so we can propagate a clearer error message.
          const notebookState = store.get(notebookAtom);
          const cellRuntime = notebookState.cellRuntime[cellId];
          const cellData = notebookState.cellData[cellId];

          const cellNotInitialized = isUninstantiated({
            executionTime:
              cellRuntime.runElapsedTimeMs ?? cellData.lastExecutionTime,
            status: cellRuntime.status,
            errored: cellRuntime.errored,
            interrupted: cellRuntime.interrupted,
            stopped: cellRuntime.stopped,
          });

          if (cellNotInitialized) {
            throw new CellNotInitializedError();
          }
        } else {
          Logger.warn(`Cell ID ${cellId} cannot be found`);
        }

        const response = await FUNCTIONS_REGISTRY.request({
          args: prettyParse(input, args[0]),
          functionName: key,
          namespace: objectId,
        });
        if (response.status.code !== "ok") {
          Logger.error(response.status);
          throw new Error(response.status.message || "Unknown error");
        }
        return prettyParse(output, response.return_value);
      };
    }

    return methods;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plugin.functions, hostElement, resetNonce]);

  // If we failed to parse the initial value, render an error
  if (!parsedResult.success) {
    return renderError(
      parsedResult.error,
      Objects.mapValues(hostElement.dataset, (value) =>
        typeof value === "string" ? parseAttrValue(value) : value,
      ),
      hostElement.shadowRoot,
    );
  }

  // Render the plugin
  return (
    <StyleNamespace>
      <div className={`contents ${theme}`}>
        <Suspense fallback={<div />}>
          {plugin.render({
            setValue: setValueAndSendInput,
            value,
            data: parsedResult.data,
            children: childNodes,
            host: hostElement,
            functions: functionMethods,
          })}
        </Suspense>
      </div>
    </StyleNamespace>
  );
}

const PluginSlot: React.ForwardRefExoticComponent<
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  PluginSlotProps<any> & React.RefAttributes<PluginSlotHandle>
> = React.forwardRef(PluginSlotInternal);

const styleSheetCache = new Map<string, CSSStyleSheet>();

const customElementLocator = "__custom_marimo_element__";

/**
 * Register a React component as a custom element
 *
 * The custom element is expected to have the attribute
 * "data-initial-value", containing an initial value for the component.
 * It may take any other attributes as well. Any attributes that are prefixed
 * with "data-" will be passed to the component as props.
 *
 * We listen on any changes to the children of the element and re-render the
 * React component when they change. Instead of unmounting the component, we
 * replace the children via a callback passed to the component.
 *
 * We also copy any local stylesheets into the shadow root of the component.
 * This is necessary because the shadow root is not part of the DOM, so it
 * cannot access stylesheets from the main document.
 * We need to wait for the stylesheets to load before rendering the component,
 * otherwise the component my flash unstyled.
 *
 * @param plugin - The plugin to register which contains the component tagName
 * and the React component to render
 */
export function registerReactComponent<T>(plugin: IPlugin<T, unknown>): void {
  const WebComponent = class extends HTMLElement implements IMarimoHTMLElement {
    private observer: MutationObserver;
    private root?: Root;
    private mounted = false;
    private pluginRef = createRef<PluginSlotHandle>();
    protected __type__ = customElementLocator;

    constructor() {
      super();
      // Create a shadow root so we can store the React tree on the shadow root, while the original
      // element's children are still on the DOM
      this.attachShadow({ mode: "open" });
      this.copyStyles();

      // This observer is used to detect changes to the children and re-render the component
      this.observer = new MutationObserver(() => {
        this.pluginRef.current?.setChildren(this.getChildren());
      });
    }

    connectedCallback() {
      // Skip mounting if this element is in the light DOM of another
      // marimo custom element. The parent element's shadow DOM will
      // re-create this element via getChildren() -> renderHTML(), so
      // this light DOM copy should remain inert to avoid duplicate
      // side-effects (e.g., mo.lazy firing load() twice).
      if (this.isLightDOMChildOfMarimoElement()) {
        return;
      }

      if (!this.mounted) {
        // Create a React root on the shadow root
        invariant(this.shadowRoot, "Shadow root should exist");
        // If we already have a root, unmount it before creating a new one
        if (this.root) {
          // This can't happen in disconnectedCallback because we want React to
          // handle the descendants unmounting.
          this.root.unmount();
        }
        this.root = ReactDOM.createRoot(this.shadowRoot);

        // Render the component for the first time
        this.mountReactComponent();
      }

      // Listen for DOM changes
      this.observer.observe(this, {
        attributes: true,
        childList: true,
        subtree: true,
        characterData: true,
      });
    }

    disconnectedCallback() {
      this.observer.disconnect();
      this.root?.unmount();
      if (this.mounted) {
        this.mounted = false;
      }
    }

    /**
     * Check if this element is in the light DOM of another marimo
     * custom element. When a marimo element (e.g. marimo-tabs) has
     * children that are also marimo elements (e.g. marimo-lazy), the
     * browser upgrades both the light DOM originals AND the shadow DOM
     * copies created by renderHTML(). The light DOM copies should not
     * mount since they are not rendered (no <slot>) and would cause
     * duplicate side-effects.
     *
     * parentElement traversal stays within the same DOM tree boundary
     * (shadow root or document), so shadow DOM copies never find a
     * marimo ancestor and correctly return false.
     */
    private isLightDOMChildOfMarimoElement(): boolean {
      let parent = this.parentElement;
      while (parent) {
        if (isCustomMarimoElement(parent)) {
          return true;
        }
        parent = parent.parentElement;
      }
      return false;
    }

    /**
     * Reset the plugin initial value and data.
     * And then re-render the plugin.
     */
    reset() {
      this.dispatchEvent(
        createInputEvent(parseAttrValue(this.dataset.initialValue), this),
      );
      this.rerender();
    }

    /**
     * Re-render the plugin.
     */
    rerender() {
      this.pluginRef.current?.reset();
    }

    /**
     * Get the children of the element as React nodes.
     */
    private getChildren(): React.ReactNode {
      // We don't sanitize the HTML here because it could be an iframe inside of tabs or accordions
      // If we have multiple children, we need to render each one separately
      if (this.children.length === 0) {
        return null;
      }
      if (this.children.length === 1) {
        return renderHTML({ html: this.innerHTML, alwaysSanitizeHtml: false });
      }
      // Multiple children - render each one
      return Array.from(this.children).map((child, index) => (
        <React.Fragment key={index}>
          {renderHTML({ html: child.outerHTML, alwaysSanitizeHtml: false })}
        </React.Fragment>
      ));
    }

    /**
     * Mount the React component to the shadow root
     */
    private async mountReactComponent() {
      this.mounted = true;

      invariant(this.root, "Root must be defined");
      this.root.render(
        <Provider store={store}>
          <LocaleProvider>
            <PluginSlot
              hostElement={this}
              plugin={plugin}
              ref={this.pluginRef}
              getInitialValue={() => {
                return parseInitialValue(this, UIElementRegistry.INSTANCE);
              }}
            >
              {this.getChildren()}
            </PluginSlot>
          </LocaleProvider>
        </Provider>,
      );
    }

    /**
     * Copy stylesheets from the main document to the shadow root
     */
    private async copyStyles() {
      const shadowRoot = this.shadowRoot;
      invariant(shadowRoot, "Shadow root should exist");
      // If we don't support adopted stylesheets, we need to copy the styles
      if (!this.isAdoptedStyleSheetsSupported()) {
        Logger.warn(
          "adoptedStyleSheets not supported, copying stylesheets in a less performance way. Please consider upgrading your browser.",
        );
        this.copyStylesFallback();
        return;
      }

      // Get all stylesheets from the main document
      const sheets = Array.from(document.styleSheets).filter((sheet) => {
        // Support for styles with Vite
        if (
          sheet.ownerNode instanceof HTMLElement &&
          sheet.ownerNode.dataset.viteDevId
        ) {
          return true;
        }
        return shouldCopyStyleSheet(sheet);
      });
      // Create new stylesheets if not already cached
      for (const sheet of sheets) {
        const sheetUniqueKey =
          sheet.href ??
          (sheet.ownerNode instanceof HTMLElement
            ? sheet.ownerNode.dataset.viteDevId
            : undefined) ??
          sheet.title;
        if (!sheetUniqueKey) {
          continue;
        }

        if (!styleSheetCache.has(sheetUniqueKey)) {
          // We need to create a new stylesheet because we can't use the same
          // stylesheet otherwise the browser will throw an error.
          const newSheet = new CSSStyleSheet();
          try {
            newSheet.replaceSync(
              Array.from(sheet.cssRules)
                .map((rule) => {
                  if (rule.cssText.includes("@import")) {
                    // @import rules are not supported in adoptedStyleSheets
                    return "";
                  }
                  return rule.cssText;
                })
                .join("\n"),
            );
          } catch {
            // It is possible that the stylesheet is not accessible due to CORS
            // We can ignore this error
          }

          styleSheetCache.set(sheetUniqueKey, newSheet);
        }
      }
      // Add all stylesheets to the shadow root
      shadowRoot.adoptedStyleSheets = [...styleSheetCache.values()];

      // Custom styles provided by the plugin
      if (plugin.cssStyles) {
        const pluginSheet = new CSSStyleSheet();
        pluginSheet.replaceSync(plugin.cssStyles.join("\n"));
        // Add plugin styles last to take precedence
        shadowRoot.adoptedStyleSheets = [
          ...shadowRoot.adoptedStyleSheets,
          pluginSheet,
        ];
      }
    }

    private copyStylesFallback() {
      const shadowRoot = this.shadowRoot;
      invariant(shadowRoot, "Shadow root should exist");

      Logger.warn(
        "adoptedStyleSheets not supported, copying stylesheets in a less performance way. Please consider upgrading your browser.",
      );

      const styleSheets = Array.from(document.styleSheets).flatMap((sheet) => {
        if (!shouldCopyStyleSheet(sheet)) {
          return [];
        }

        const style = document.createElement("style");
        try {
          style.textContent = Array.from(sheet.cssRules)
            .map((rule) => rule.cssText)
            .join("\n");
        } catch {
          // It is possible that the stylesheet is not accessible due to CORS
          // We can ignore this error
          return [];
        }

        return [style];
      });

      shadowRoot.append(...styleSheets);

      // Custom styles provided by the plugin
      if (plugin.cssStyles) {
        const style = document.createElement("style");
        style.textContent = plugin.cssStyles.join("\n");
        shadowRoot.append(style);
      }
    }

    private isAdoptedStyleSheetsSupported() {
      return (
        "adoptedStyleSheets" in Document.prototype &&
        "replace" in CSSStyleSheet.prototype
      );
    }
  };

  defineCustomElement(plugin.tagName, WebComponent);
}

// Copy the stylesheet to the shadow root if it is local
// or from our assetUrl (in the case of a static notebook)
//
// This logic is not for security reasons, but rather to
// avoid pollution of various 3rd party stylesheets
function shouldCopyStyleSheet(sheet: CSSStyleSheet): boolean {
  // Copy local stylesheets owned by marimo
  if (sheet.title?.startsWith("marimo")) {
    return true;
  }

  if (!sheet.href) {
    return false;
  }

  // Must stylesheet must end with .css
  if (!sheet.href.endsWith(".css")) {
    return false;
  }

  // Copy stylesheets from localhost in development mode
  if (
    sheet.href.includes("127.0.0.1") &&
    (process.env.NODE_ENV === "test" || process.env.NODE_ENV === "development")
  ) {
    return true;
  }

  // Copy stylesheets from our NPM package
  if (sheet.href.includes("/@marimo-team/")) {
    return true;
  }

  // Copy stylesheets served from the same origin
  return sheet.href.startsWith(window.location.origin);
}

export function isCustomMarimoElement(
  element: Element | null,
): element is IMarimoHTMLElement {
  if (!element) {
    return false;
  }
  if (!(element instanceof HTMLElement)) {
    return false;
  }

  return "__type__" in element && element.__type__ === customElementLocator;
}

function prettyParse<T>(schema: z.ZodType<T>, data: unknown): T {
  const result = schema.safeParse(data);
  if (!result.success) {
    Logger.log("Failed to parse data", data, result.error);
    throw new Error(z.prettifyError(result.error));
  }
  return result.data;
}
