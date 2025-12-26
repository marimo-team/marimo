/* Copyright 2026 Marimo. All rights reserved. */

import { acceptCompletion } from "@codemirror/autocomplete";
import type { Language } from "@codemirror/language";
import { type Extension, Prec } from "@codemirror/state";
import { type EditorView, keymap, type TooltipView } from "@codemirror/view";
import {
  hoverResource,
  type Resource,
  resourceCompletion,
  resourceDecorations,
  resourceInputFilter,
  resourcesField,
  resourceTheme,
} from "@marimo-team/codemirror-mcp";
import {
  getAIContextRegistry,
  getFileContextProvider,
} from "@/core/ai/context/context";
import type { AIContextItem } from "@/core/ai/context/registry";
import type { JotaiStore } from "@/core/state/jotai";
import { Logger } from "@/utils/Logger";
import { contextCallbacks } from "./state";

const NONE_RESOURCE_TYPE = "_none_";
const NONE_RESOURCE = [
  {
    uri: "",
    name: "No resources",
    type: NONE_RESOURCE_TYPE,
    data: {},
  },
];
const NONE_RESOURCE_FORMAT_COMPLETION = {
  info: "Variables, dataframes, and tables will appear here.",
  apply: () => {
    return;
  },
};

export function resourceExtension(opts: {
  language: Language;
  store: JotaiStore;
  onAddFiles?: (files: File[]) => void;
}): Extension[] {
  const { language, store, onAddFiles } = opts;

  return [
    language.data.of({
      // Resource completion for static resources (variables, tables, etc.)
      autocomplete: resourceCompletion(
        async (): Promise<Resource[]> => {
          const registry = getAIContextRegistry(store);
          const resources = registry.getAllItems();
          if (resources.length === 0) {
            return NONE_RESOURCE;
          }
          return resources;
        },
        (resource) => {
          if (resource.type === NONE_RESOURCE_TYPE) {
            return NONE_RESOURCE_FORMAT_COMPLETION;
          }

          const registry = getAIContextRegistry(store);
          const provider = registry.getProvider(resource.type);
          return provider?.formatCompletion(resource as AIContextItem) || {};
        },
      ),
    }),
    Prec.high(
      keymap.of([
        {
          key: "Tab",
          run: (view: EditorView) => {
            return acceptCompletion(view);
          },
        },
      ]),
    ),
    contextCallbacks.of({
      addAttachment: (attachment) => onAddFiles?.([attachment]),
    }),
    // Dynamic file completion
    ...(onAddFiles
      ? [
          language.data.of({
            autocomplete: getFileContextProvider().createCompletionSource(),
          }),
        ]
      : []),
    resourceDecorations,
    resourceInputFilter,
    resourcesField.init(() => {
      const registry = getAIContextRegistry(store);
      const resources = registry.getAllItems();
      return new Map(resources.map((resource) => [resource.uri, resource]));
    }),
    resourceTheme,
    hoverResource({
      createTooltip: (resource): TooltipView => {
        const registry = getAIContextRegistry(store);
        const provider = registry.getProvider(resource.type);
        if (!provider) {
          Logger.warn("No provider found for resource", resource);
          return asDom(resource.description || resource.name);
        }
        const completion = provider.formatCompletion(resource as AIContextItem);
        const fallback = resource.description || resource.name;
        if (!completion?.info) {
          return asDom(fallback);
        }
        if (typeof completion.info === "string") {
          return asDom(completion.info);
        }
        const info = completion.info(completion);
        if (!info) {
          return asDom(fallback);
        }
        if ("dom" in info) {
          return {
            dom: info.dom as HTMLElement,
          };
        }
        if ("then" in info) {
          Logger.warn("info is a promise. This is not supported", info);
          return asDom(fallback);
        }
        return {
          dom: info as HTMLElement,
        };
      },
    }),
  ];
}

function asDom(value: string): TooltipView {
  const tooltip = document.createElement("div");
  tooltip.innerHTML = value;
  return {
    dom: tooltip,
  };
}
