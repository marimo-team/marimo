/* Copyright 2023 Marimo. All rights reserved. */
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
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import ReactDOM, { Root } from "react-dom/client";

import {
  createInputEvent,
  marimoValueUpdateEvent,
  MarimoValueUpdateEventType,
} from "@/core/dom/events";
import { defineCustomElement } from "../../core/dom/defineCustomElement";
import { parseAttrValue, parseInitialValue } from "../../core/dom/htmlUtils";
import { IPlugin } from "../types";
import { Objects } from "../../utils/objects";
import { renderError } from "./BadPlugin";
import { renderHTML } from "./RenderHTML";
import { invariant } from "../../utils/invariant";
import { Logger } from "../../utils/Logger";
import { getTheme } from "@/theme/useTheme";

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
  ref: React.Ref<PluginSlotHandle>
): JSX.Element {
  const [childNodes, setChildNodes] = useState<ReactNode>(children);
  const [value, setValue] = useState<T>(getInitialValue());

  const [parseResult, setParseResult] = useState(() => {
    return plugin.validator.safeParse({
      // For any string values, unescape/parse them
      ...Objects.mapValues(hostElement.dataset, (value) =>
        typeof value === "string" ? parseAttrValue(value) : value
      ),
    });
  });

  useImperativeHandle(ref, () => ({
    reset: () => {
      setValue(getInitialValue());
      setParseResult(
        plugin.validator.safeParse({
          // For any string values, unescape/parse them
          ...Objects.mapValues(hostElement.dataset, (value) =>
            typeof value === "string" ? parseAttrValue(value) : value
          ),
        })
      );
    },
    setChildren: (children) => {
      setChildNodes(children);
    },
  }));

  // When the component's value changes due to an interaction, an input
  // event should be dispatched; an event should not be dispatched when
  // the value changes due to an update event broadcast by another component.
  // TODO: is this still needed ...? might want to dispatch value update
  // even when value hasn't changed (so python kernel gets triggered ...)
  const shouldDispatchInput = useRef(false);

  if (shouldDispatchInput.current) {
    hostElement.dispatchEvent(createInputEvent(value, hostElement));
    shouldDispatchInput.current = false;
  }

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
          mutation.attributeName?.startsWith("data-")
      );
      if (hasAttributeMutation) {
        setParseResult(
          plugin.validator.safeParse({
            // For any string values, unescape/parse them
            ...Objects.mapValues(hostElement.dataset, (value) =>
              typeof value === "string" ? parseAttrValue(value) : value
            ),
          })
        );
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

  const setValueAndSendInput = useCallback(
    (value: T | ((prevValue: T) => T)): void => {
      shouldDispatchInput.current = true;
      setValue(value);
    },
    [setValue, shouldDispatchInput]
  );

  // If we failed to parse the initial value, render an error
  if (!parseResult.success) {
    return renderError(parseResult.error);
  }

  // Render the plugin
  const theme = getTheme();
  return (
    <div className={`contents ${theme}`}>
      {plugin.render({
        setValue: setValueAndSendInput,
        value,
        data: parseResult.data,
        children: childNodes,
        host: hostElement,
      })}
    </div>
  );
}

const PluginSlot: React.ForwardRefExoticComponent<
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  PluginSlotProps<any> & React.RefAttributes<PluginSlotHandle>
> = React.forwardRef(PluginSlotInternal);

const styleSheetCache = new Map<string, CSSStyleSheet>();

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
  const WebComponent = class extends HTMLElement {
    private observer: MutationObserver;
    private root?: Root;
    private mounted = false;
    private pluginRef = createRef<PluginSlotHandle>();

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
        </PluginSlot>
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
          sheet.ownerNode.dataset["viteDevId"]
        ) {
          return true;
        }
        // Only copy stylesheets that point to our domain
        return sheet.href && sheet.href.startsWith(window.location.origin);
      });
      // Create new stylesheets if not already cached
      for (const sheet of sheets) {
        const sheetUniqueKey =
          sheet.href ??
          (sheet.ownerNode instanceof HTMLElement
            ? sheet.ownerNode.dataset["viteDevId"]
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
              .join("\n")
          );
          styleSheetCache.set(sheetUniqueKey, newSheet);
        }
      }
      // Add all stylesheets to the shadow root
      shadowRoot.adoptedStyleSheets = [...styleSheetCache.values()];
    }

    private copyStylesFallback() {
      const shadowRoot = this.shadowRoot;
      invariant(shadowRoot, "Shadow root should exist");

      Logger.warn(
        "adoptedStyleSheets not supported, copying stylesheets in a less performance way. Please consider upgrading your browser."
      );

      const styleSheets = Array.from(document.styleSheets).flatMap((sheet) => {
        // Only copy stylesheets that point to our domain
        if (!sheet.href || !sheet.href.startsWith(window.location.origin)) {
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
