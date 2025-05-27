/* Copyright 2024 Marimo. All rights reserved. */
import type { QuotePrefixKind } from "../utils/quotes";

// Based on the current quote prefix and the checkbox state, return the new quote prefix
export function getQuotePrefix(
  currentQuotePrefix: QuotePrefixKind,
  checked: boolean,
  prefix: QuotePrefixKind,
) {
  let newQuotePrefix = currentQuotePrefix;
  if (checked) {
    // Add a prefix
    if (currentQuotePrefix === "") {
      newQuotePrefix = prefix;
    } else if (currentQuotePrefix !== "rf" && prefix !== currentQuotePrefix) {
      newQuotePrefix = "rf";
    }
  } else {
    // Removing a prefix
    if (currentQuotePrefix === prefix) {
      // Removing the only prefix
      newQuotePrefix = "";
    } else if (currentQuotePrefix === "rf") {
      newQuotePrefix = prefix === "r" ? "f" : "r";
    }
  }

  return newQuotePrefix;
}

export const MarkdownQuotePrefixTooltip: React.FC = () => {
  return (
    <div className="flex flex-col gap-3.5">
      <section className="flex flex-col gap-0.5">
        <header className="flex items-center gap-1">
          <code className="text-xs px-1 py-0.5 bg-[var(--slate-2)] rounded">
            r
          </code>
          <span className="font-semibold">Raw String</span>
        </header>
        <p className="text-sm text-muted-foreground">
          Write LaTeX without escaping special characters
        </p>
        <pre className="text-xs bg-[var(--slate-2)] p-2 rounded">
          \alpha \beta
        </pre>
      </section>

      <section className="flex flex-col gap-0.5">
        <header className="flex items-center gap-1">
          <code className="text-xs px-1 py-0.5 bg-[var(--slate-2)] rounded">
            f
          </code>
          <span className="font-semibold">Format String</span>
        </header>
        <p className="text-sm text-muted-foreground">
          Interpolate Python values
        </p>
        <pre className="text-xs bg-[var(--slate-2)] p-2 rounded">
          Hello {"{name}"}! 😁
        </pre>
      </section>
    </div>
  );
};
