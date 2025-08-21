/* Copyright 2024 Marimo. All rights reserved. */

import type { Language } from "@codemirror/language";
import type { Extension } from "@codemirror/state";
import type { TooltipView } from "@codemirror/view";
import {
  hoverResource,
  type Resource,
  resourceCompletion,
  resourceDecorations,
  resourceInputFilter,
  resourcesField,
  resourceTheme,
} from "@marimo-team/codemirror-mcp";
import { getAIContextRegistry } from "@/core/ai/context/context";
import type { AIContextItem } from "@/core/ai/context/registry";
import type { JotaiStore } from "@/core/state/jotai";
import { Logger } from "@/utils/Logger";

export function resourceExtension(
  language: Language,
  store: JotaiStore,
): Extension[] {
  return [
    language.data.of({
      autocomplete: resourceCompletion(
        async (): Promise<Resource[]> => {
          const registry = getAIContextRegistry(store);
          const resources = registry.getAllItems();
          return resources;
        },
        (resource) => {
          const registry = getAIContextRegistry(store);
          const provider = registry.getProvider(resource.type);
          return provider?.formatCompletion(resource as AIContextItem) || {};
        },
      ),
    }),
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
