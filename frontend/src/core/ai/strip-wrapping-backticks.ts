/* Copyright 2026 Marimo. All rights reserved. */

const LANGS = ["python", "sql", "markdown"] as const;

interface StripOptions {
  /**
   * When true, the text is treated as a partial stream:
   * - the opening fence is only stripped once we can be sure of its language
   *   identifier (e.g. "```py" is left untouched since it may still become
   *   "```python"), and
   * - the closing fence is left in place, since it may not have arrived yet (or
   *   a trailing "```" may be part of the content).
   */
  streaming?: boolean;
}

/**
 * Removes wrapping markdown code fences from a completion string.
 */
export function stripWrappingBackticks(
  text: string,
  opts: StripOptions = {},
): string {
  const { streaming = false } = opts;
  const leadingWhitespace = text.match(/^\s*/)?.[0] ?? "";
  const rest = text.slice(leadingWhitespace.length);

  let body: string | null = null;
  let strippedOpening = false;

  for (const lang of LANGS) {
    if (rest.startsWith(`\`\`\`${lang}`)) {
      strippedOpening = true;
      body = rest.slice(3 + lang.length);
      if (body.startsWith("\n")) {
        body = body.slice(1);
      }
      break;
    }
  }

  if (!strippedOpening && rest.startsWith("```")) {
    const afterFence = rest.slice(3);
    if (streaming && isPartialLanguageFence(afterFence)) {
      return text;
    }
    strippedOpening = true;
    body = afterFence;
    if (body.startsWith("\n")) {
      body = body.slice(1);
    }
  }

  if (!strippedOpening || body === null) {
    return text;
  }

  // While streaming, the closing fence may not have arrived yet, so leave the
  // body as-is once the opening fence is removed.
  if (streaming) {
    return body;
  }

  const strippedEnd = body.trimEnd();
  const trailingSpace = body.slice(strippedEnd.length);

  if (strippedEnd.endsWith("\n```")) {
    return strippedEnd.slice(0, -4) + trailingSpace;
  }
  if (strippedEnd.endsWith("```")) {
    return strippedEnd.slice(0, -3) + trailingSpace;
  }

  return body;
}

/**
 * Returns true if the text after an opening "```" has no terminating newline
 * yet and could still become a known language identifier.
 */
function isPartialLanguageFence(afterFence: string): boolean {
  // Once the first line is terminated, we already know it is not a known
  // language fence (those are handled above), so treat it as a plain fence.
  if (afterFence.includes("\n")) {
    return false;
  }
  return LANGS.some((lang) => lang.startsWith(afterFence));
}
