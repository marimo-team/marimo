/* Copyright 2024 Marimo. All rights reserved. */
import type { CompletionResult } from "@codemirror/autocomplete";

import type {
  CompletionOption,
  CompletionResultMessage,
} from "../../kernel/messages";
import { sendCodeCompletionRequest } from "@/core/network/requests";
import type { Tooltip } from "@codemirror/view";
import { DeferredRequestRegistry } from "@/core/network/DeferredRequestRegistry";
import type { CodeCompletionRequest } from "@/core/network/types";
import "../../../components/editor/documentation.css";

function constructCompletionInfoNode(
  innerHtml?: string | null,
): HTMLElement | null {
  if (!innerHtml) {
    return null;
  }
  const container = document.createElement("span");
  container.classList.add("mo-cm-tooltip");
  container.classList.add("docs-documentation");
  container.style.display = "flex";
  container.style.flexDirection = "column";
  container.style.gap = ".8rem";
  container.innerHTML = innerHtml;
  return container;
}

export const AUTOCOMPLETER = new DeferredRequestRegistry<
  Omit<CodeCompletionRequest, "id">,
  CompletionResultMessage | null
>(
  "autocomplete-result",
  async (requestId, req) => {
    await sendCodeCompletionRequest({
      id: requestId,
      ...req,
    });
  },
  // We don't resolve previous requests
  // because they may be used for tooltips or live documentation.
);

const BOOSTS: Record<CompletionOption["type"], number> = {
  param: 3,
  property: 2,
  // everything else is equal so alphabetically sorted
};

export const Autocompleter = {
  /**
   * Convert a CompletionResultMessage to a CompletionResult
   */
  asCompletionResult(
    position: number,
    message: CompletionResultMessage,
  ): CompletionResult {
    return {
      from: position - message.prefix_length,
      options: message.options.map((option) => {
        return {
          label: option.name,
          type: option.type,
          // Boost params so they appear first
          // This appears inside parentheses
          boost: BOOSTS[option.type] ?? 1,
          info: () => constructCompletionInfoNode(option.completion_info),
        };
      }),
      validFor: /^\w*$/,
    };
  },

  /**
   * Convert a CompletionResultMessage to a Tooltip
   */
  asHoverTooltip({
    position,
    message,
    limitToType,
    excludeTypes,
    exactName,
  }: {
    position: number;
    message: CompletionResultMessage;
    limitToType?: "tooltip";
    excludeTypes?: string[];
    exactName?: string;
  }): (Tooltip & { html?: string | null }) | undefined {
    const firstOption = getFirstOption(message.options, exactName);
    if (!firstOption) {
      return undefined;
    }

    const from = position - message.prefix_length;
    const dom = constructCompletionInfoNode(firstOption.completion_info);
    if (!dom) {
      return;
    }

    if (limitToType && firstOption.type !== limitToType) {
      return;
    }

    if (excludeTypes?.includes(firstOption.type)) {
      return;
    }

    return {
      pos: from,
      html: firstOption.completion_info,
      end: from + firstOption.name.length,
      above: true,
      create: () => ({ dom, resize: false }),
    };
  },
};

function getFirstOption(
  options: CompletionOption[],
  tieBreak?: string,
): CompletionOption | undefined {
  if (options.length === 0) {
    return undefined;
  }
  if (options.length === 1) {
    // One option
    return options[0];
  }
  if (tieBreak) {
    // Tie break to a matching name
    return options.find((option) => option.name === tieBreak);
  }
  return undefined;
}
