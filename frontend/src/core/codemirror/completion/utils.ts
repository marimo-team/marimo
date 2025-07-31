/* Copyright 2024 Marimo. All rights reserved. */
import type { CompletionSource } from "@codemirror/autocomplete";
import type { EditorState } from "@codemirror/state";

/**
 * Condition CompletionSource
 */
export function conditionalCompletion(opts: {
  completion: CompletionSource;
  predicate: (state: EditorState) => boolean;
}): CompletionSource {
  return (ctx) => {
    if (!opts.predicate(ctx.state)) {
      return null;
    }
    return opts.completion(ctx);
  };
}
