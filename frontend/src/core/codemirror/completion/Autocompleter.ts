/* Copyright 2023 Marimo. All rights reserved. */
import { CompletionResult } from "@codemirror/autocomplete";

import { Deferred } from "../../../utils/Deferred";
import {
  CompletionOption,
  CompletionResultMessage,
} from "../../kernel/messages";
import { generateUUID } from "@/utils/uuid";
import { CellId } from "@/core/model/ids";
import { sendCodeCompletionRequest } from "@/core/network/requests";
import { Tooltip } from "@codemirror/view";

interface Entry {
  deferred: Deferred<CompletionResultMessage>;
  pos: number;
}

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

export class Autocompleter {
  public static INSTANCE = new Autocompleter();

  // TODO: maybe we store at most one request, evicting old ones
  private requests = new Map<string, Entry>();

  private constructor() {
    // Singleton
  }

  /**
   * Request completions for the given query
   */
  async request(opts: {
    pos: number;
    query: string;
    cellId: CellId;
  }): Promise<CompletionResultMessage> {
    const completionId = generateUUID();
    const deferred = new Deferred<CompletionResultMessage>();

    this.requests.set(completionId, { deferred: deferred, pos: opts.pos });

    // On failures, remove the request and rethrow the error
    deferred.promise.catch((error) => {
      this.requests.delete(completionId);
      throw error;
    });

    await sendCodeCompletionRequest(completionId, opts.query, opts.cellId);
    return deferred.promise;
  }

  resolve(msg: CompletionResultMessage) {
    const entry = this.requests.get(msg.completion_id);
    if (entry === undefined) {
      return;
    }

    entry.deferred.resolve(msg);
    this.requests.delete(msg.completion_id);
  }

  /**
   * Convert a CompletionResultMessage to a CompletionResult
   */
  static asCompletionResult(
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
  }

  /**
   * Convert a CompletionResultMessage to a Tooltip
   */
  static asHoverTooltip({
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
  }
}
