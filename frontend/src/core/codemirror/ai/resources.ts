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
          console.warn("resourceCompletion", resources);
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
    resourcesField,
    resourceTheme,
    hoverResource({
      createTooltip: (resource): TooltipView => {
        const provider = registry.getProvider(resource.type);
        const completion = provider?.formatCompletion(
          resource as AIContextItem,
        );
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
        return asDom(fallback);
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
