/* Copyright 2023 Marimo. All rights reserved. */
import { CompletionResult } from "@codemirror/autocomplete";

import {
  CompletionOption,
  CompletionResultMessage,
} from "../../kernel/messages";
import { sendCodeCompletionRequest } from "@/core/network/requests";
import { Tooltip } from "@codemirror/view";
import { DeferredRequestRegistry } from "@/core/network/DeferredRequestRegistry";
import { CodeCompletionRequest } from "@/core/network/types";

function constructCompletionInfoNode(innerHtml?: string): HTMLElement | null {
  if (!innerHtml) {
    return null;
  }
  const container = document.createElement("span");
  container.classList.add("mo-cm-tooltip");
  container.style.display = "flex";
  container.style.flexDirection = "column";
  container.style.gap = "1rem";
  container.innerHTML = innerHtml;
  return container;
}

export const AUTOCOMPLETER = new DeferredRequestRegistry<
  Omit<CodeCompletionRequest, "id">,
  CompletionResultMessage
>("function-call-result", async (requestId, req) => {
  await sendCodeCompletionRequest({
    id: requestId,
    ...req,
  });
});

export const Autocompleter = {
  /**
   * Convert a CompletionResultMessage to a CompletionResult
   */
  asCompletionResult(
    position: number,
    message: CompletionResultMessage
  ): CompletionResult {
    return {
      from: position - message.prefix_length,
      options: message.options.map((option) => {
        return {
          label: option.name,
          type: option.type,
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
    exactName,
  }: {
    position: number;
    message: CompletionResultMessage;
    limitToType?: "tooltip";
    exactName?: string;
  }): Tooltip | undefined {
    const options = [...message.options];

    let firstOption: CompletionOption | undefined;
    // If there are no options, don't show a tooltip
    if (options.length === 0) {
      return undefined;
    } else if (options.length === 1) {
      // One option
      firstOption = options[0];
    } else if (exactName) {
      // Tie break to a matching name
      firstOption = options.find((option) => option.name === exactName);
    }

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

    return {
      pos: from,
      end: from + firstOption.name.length,
      above: true,
      create: () => ({ dom, resize: false }),
    };
  },
};
