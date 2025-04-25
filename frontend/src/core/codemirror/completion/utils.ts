import type { CompletionSource } from "@codemirror/autocomplete";

/**
 * Condition CompletionSource
 */
export function conditionalCompletion(opts: {
  completion: CompletionSource;
  predicate: () => boolean;
}): CompletionSource {
  return (ctx) => {
    if (!opts.predicate()) {
      return null;
    }
    return opts.completion(ctx);
  };
}
