/* Copyright 2023 Marimo. All rights reserved. */
import { CompletionResult } from "@codemirror/autocomplete";

import { Deferred } from "../../../utils/Deferred";
import {
  CompletionOption,
  CompletionResultMessage,
} from "../../kernel/messages";

interface Entry {
  deferred: Deferred<CompletionResult>;
  pos: number;
}

function constructCompletionInfoNode(innerHtml?: string): Node | null {
  if (!innerHtml) {
    return null;
  }
  const container = document.createElement("span");
  container.style.display = "flex";
  container.style.flexDirection = "column";
  container.style.gap = "1rem";
  container.innerHTML = innerHtml;
  return container;
}

class CompletionRequests {
  // TODO: maybe we store at most one request, evicting old ones
  private requests = new Map<string, Entry>();

  has(completionId: string): boolean {
    return this.requests.has(completionId);
  }

  register(
    completionId: string,
    deferred: Deferred<CompletionResult>,
    pos: number
  ) {
    this.requests.set(completionId, { deferred: deferred, pos: pos });
    // On failures, remove the request and rethrow the error
    deferred.promise.catch((error) => {
      this.requests.delete(completionId);
      throw error;
    });
  }

  resolve(msg: CompletionResultMessage) {
    const entry = this.requests.get(msg.completion_id);
    if (entry === undefined) {
      return;
    }

    entry.deferred.resolve({
      from: entry.pos - msg.prefix_length,
      options: msg.options.map((o: CompletionOption) => {
        return {
          label: o.name,
          type: o.type,
          info: () => constructCompletionInfoNode(o.completion_info),
        };
      }),
      validFor: /^\w*$/,
    });
    this.requests.delete(msg.completion_id);
  }
}

export const COMPLETION_REQUESTS = new CompletionRequests();
