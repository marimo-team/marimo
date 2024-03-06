/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable unicorn/prefer-spread */
/**
 * WebComponent Factory for React Components
 *
 * Provides a factory for defining a custom web component from a React
 * component. The factory handles the logic of communicating UI element values
 * to and from the rest of marimo.
 */
import React, {
  createRef,
  ReactNode,
  SetStateAction,
  Suspense,
  useEffect,
  useImperativeHandle,
  useMemo,
  useState,
} from "react";
import ReactDOM, { Root } from "react-dom/client";

import {
  createInputEvent,
  marimoValueUpdateEvent,
  MarimoValueUpdateEventType,
} from "@/core/dom/events";
import { defineCustomElement } from "../../core/dom/defineCustomElement";
import {
  parseAttrValue,
  parseDataset,
  parseInitialValue,
} from "../../core/dom/htmlUtils";
import { IPlugin } from "../types";
import { Objects } from "../../utils/objects";
import { renderError } from "./BadPlugin";
import { renderHTML } from "./RenderHTML";
import { invariant } from "../../utils/invariant";
import { Logger } from "../../utils/Logger";
import { useTheme } from "@/theme/useTheme";
import { FUNCTIONS_REGISTRY } from "@/core/functions/FunctionRegistry";
import { getUIElementObjectId } from "@/core/dom/UIElement";
import { PluginFunctions } from "./rpc";
import { ZodSchema } from "zod";
import useEvent from "react-use-event-hook";
import { Functions } from "@/utils/functions";
import {
  getStaticNotebookAssetUrl,
  isStaticNotebook,
} from "@/core/static/static-state";

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

  useImperativeHandle(ref, () => ({
    reset: () => {
      setValue(getInitialValue());
      setParsedResult(plugin.validator.safeParse(parseDataset(hostElement)));
    },
    setChildren: (children) => {
      setChildNodes(children);
    },
  }));

  useEffect(() => {
    const handleValue = (e: MarimoValueUpdateEventType) => {
      if (e.detail.element === hostElement) {
        setValue(e.detail.value as T);
      }
    };
    // We create a mutation observer to listen for changes to the host element's attributes
    // and update the plugin's data accordingly
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

    // Create listeners
    hostElement.addEventListener(marimoValueUpdateEvent, handleValue);
    observer.observe(hostElement, {
      attributes: true, // configure it to listen to attribute changes
    });

    return () => {
      // Remove listeners
      hostElement.removeEventListener(marimoValueUpdateEvent, handleValue);
      observer.disconnect();
    };
  }, [hostElement, plugin.validator]);

  // When the value changes, send an input event
  const setValueAndSendInput = useEvent((value: SetStateAction<T>): void => {
    setValue((prevValue) => {
      const updater = Functions.asUpdater(value);
      const nextValue = updater(prevValue);
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
        input: ZodSchema<unknown>;
        output: ZodSchema<unknown>;
      };
      methods[key] = async (...args: unknown[]) => {
        invariant(
          args.length <= 1,
          `Plugin functions only supports a single argument. Called ${key}`,
        );
        const objectId = getUIElementObjectId(hostElement);
        invariant(objectId, "Object ID should exist");
        const response = await FUNCTIONS_REGISTRY.request({
          args: input.parse(args[0]),
          functionName: key,
          namespace: objectId,
        });
        if (response.status.code !== "ok") {
          Logger.error(response.status);
          throw new Error(response.status.message);
        }
        return output.parse(response.return_value);
      };
    }

    return methods;
  }, [plugin.functions, hostElement]);

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
      return renderHTML({ html: this.innerHTML });
    }

    /**
     * Mount the React component to the shadow root
     */
    private async mountReactComponent() {
      this.mounted = true;

      invariant(this.root, "Root must be defined");
      this.root.render(
        <PluginSlot
          hostElement={this}
          plugin={plugin}
          ref={this.pluginRef}
          getInitialValue={() => {
            return parseInitialValue(this);
          }}
        >
          {this.getChildren()}
        </PluginSlot>,
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
            : undefined);
        if (!sheetUniqueKey) {
          continue;
        }

        if (!styleSheetCache.has(sheetUniqueKey)) {
          // We need to create a new stylesheet because we can't use the same
          // stylesheet otherwise the browser will throw an error.
          const newSheet = new CSSStyleSheet();
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
          styleSheetCache.set(sheetUniqueKey, newSheet);
        }
      }
      // Add all stylesheets to the shadow root
      shadowRoot.adoptedStyleSheets = [...styleSheetCache.values()];

      // Custom styles provided by the plugin
      if (plugin.cssStyles) {
        const style = document.createElement("style");
        style.textContent = plugin.cssStyles.join("\n");
        shadowRoot.append(style);
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
        style.textContent = Array.from(sheet.cssRules)
          .map((rule) => rule.cssText)
          .join("\n");
        return [style];
      });

      shadowRoot.append(...styleSheets);
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
function shouldCopyStyleSheet(sheet: CSSStyleSheet): boolean {
  if (!sheet.href) {
    return false;
  }

  if (isStaticNotebook()) {
    return sheet.href.startsWith(getStaticNotebookAssetUrl());
  }

  if (sheet.href.startsWith("https://cdn.jsdelivr.net/npm/@marimo-team/")) {
    return true;
  }

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
