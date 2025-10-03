/* Copyright 2024 Marimo. All rights reserved. */

import { AnsiUp } from "ansi_up";
import { Logger } from "./Logger";

// Create a shared AnsiUp instance
const ansiUp = new AnsiUp();

/**
 * Extracts plain text content from HTML by removing all HTML tags and normalizing whitespace.
 *
 * @param htmlString The HTML string to parse
 * @returns Plain text content with HTML tags removed and whitespace normalized
 */
export function parseHtmlContent(htmlString: string): string {
  try {
    // Create a temporary DOM element to parse HTML
    const tempDiv = document.createElement("div");
    tempDiv.innerHTML = htmlString;

    // Extract text content, removing HTML tags
    const textContent = tempDiv.textContent || tempDiv.innerText || "";
    const lines = textContent.split("\n");
    return lines.map((line) => line.trimEnd()).join("\n");
  } catch (error) {
    Logger.error("Error parsing HTML content:", error);
    // If parsing fails, return the original string
    return htmlString;
  }
}

/**
 * Converts ANSI escape sequences to plain text by first converting to HTML and then stripping HTML tags.
 * This is useful for console output that may contain ANSI color codes or formatting.
 *
 * @param ansiString String that may contain ANSI escape sequences
 * @returns Plain text with ANSI codes removed and HTML stripped
 */
export function ansiToPlainText(ansiString: string): string {
  if (!ansiString) {
    return "";
  }

  try {
    // Convert ANSI escape sequences to HTML
    const htmlString = ansiUp.ansi_to_html(ansiString);

    // Strip HTML tags and return clean text
    return parseHtmlContent(htmlString);
  } catch (error) {
    Logger.error("Error converting ANSI to plain text:", error);
    // If conversion fails, return the original string
    return ansiString;
  }
}
