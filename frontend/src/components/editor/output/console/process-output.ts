import type { OutputMessage } from "@/core/kernel/messages";
import { ansiToPlainText, parseHtmlContent } from "@/utils/dom";
import { Strings } from "@/utils/strings";

/** Convert cell or console output to a string, while handling html and ansi codes */
export function processOutput(output: OutputMessage): string {
  if (
    output.mimetype.startsWith("application/vnd.marimo") ||
    output.mimetype === "text/html"
  ) {
    return parseHtmlContent(Strings.asString(output.data));
  }

  // Convert ANSI to HTML, then parse as HTML
  return ansiToPlainText(Strings.asString(output.data));
}
