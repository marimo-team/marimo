/* Copyright 2024 Marimo. All rights reserved. */

import { AnsiUp } from "ansi_up";
import parse, { type DOMNode, Text } from "html-react-parser";
import React, { useMemo } from "react";
import { useInstallPackages } from "@/core/packages/useInstallPackage";
import { Events } from "@/utils/events";
import { parseContent } from "@/utils/url-parser";

const ansiUp = new AnsiUp();

/**
 * Helper to clean ANSI escape codes from text
 */
export const cleanAnsiCodes = (text: string): string => {
  // Remove ANSI escape sequences (ESC[ followed by numbers/semicolons and 'm')
  // Using String.fromCharCode to avoid linter error
  const ansiRegex = new RegExp(`${String.fromCharCode(27)}\\[[0-9;]*m`, "g");
  return text.replaceAll(ansiRegex, "");
};

// Regex to match install commands: pip install, uv add, uv pip install
const INSTALL_COMMAND_REGEX =
  /(pip\s+install|uv\s+add|uv\s+pip\s+install)\s+/gi;

/**
 * Parse install command to extract a single package name
 * Supports: pip install, uv add, uv pip install
 * Handles flags like -U, --upgrade that can appear before or after the package name
 */
function parsePipInstallCommand(
  text: string,
): { package: string; endIndex: number } | null {
  INSTALL_COMMAND_REGEX.lastIndex = 0;
  const match = INSTALL_COMMAND_REGEX.exec(text);
  if (!match) {
    return null;
  }

  const commandEndIndex = match.index + match[0].length;
  const afterCommand = text.slice(commandEndIndex);

  // Skip any flags (tokens starting with -)
  // Split by whitespace and find the first non-flag token
  const tokens = afterCommand.split(/\s+/);
  let packageName = "";
  let packageStartOffset = 0;

  for (const token_ of tokens) {
    const token = token_.trim();
    if (!token) {
      continue;
    }

    // Skip flags (anything starting with -)
    if (token.startsWith("-")) {
      // Add to offset: token length + space
      packageStartOffset += token.length + 1;
      continue;
    }

    // Found the package name - extract it using character matching
    // Match until we hit a character that's not valid in package names
    const packageMatch = token.match(/^[\w,.[\]-]+/);
    if (packageMatch) {
      packageName = packageMatch[0];
      break;
    }

    break;
  }

  if (!packageName) {
    return null;
  }

  const endIndex = commandEndIndex + packageStartOffset + packageName.length;

  return { package: packageName, endIndex };
}

/**
 * Type for a replacer function that can transform DOM nodes during parsing
 * Returns a React element, string, boolean, null, or undefined (to skip replacement)
 */
type Replacer = (
  domNode: DOMNode,
) => React.ReactElement | string | boolean | null | undefined;

/**
 * Helper function to process text content for URLs and images
 * This is used by multiple replacers to avoid code duplication
 */
export function processTextForUrls(
  text: string,
  keyPrefix = "",
): React.ReactNode {
  if (!text) {
    return null;
  }

  // Quick check to avoid unnecessary parsing
  if (!/https?:\/\//.test(text)) {
    return text;
  }

  const parts = parseContent(text);

  // If no URLs detected, return original text
  if (parts.length === 1 && parts[0].type === "text") {
    return text;
  }

  // Render parts with clickable links
  return (
    <>
      {parts.map((part, idx) => {
        const key = keyPrefix ? `${keyPrefix}-${idx}` : idx;
        if (part.type === "url") {
          const cleanUrl = cleanAnsiCodes(part.url);
          return (
            <a
              key={key}
              href={cleanUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={Events.stopPropagation()}
              className="text-link hover:underline"
            >
              {cleanUrl}
            </a>
          );
        }
        if (part.type === "image") {
          // For console output, just render images as links
          const cleanUrl = cleanAnsiCodes(part.url);
          return (
            <a
              key={key}
              href={cleanUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={Events.stopPropagation()}
              className="text-link hover:underline"
            >
              {cleanUrl}
            </a>
          );
        }
        return <React.Fragment key={key}>{part.value}</React.Fragment>;
      })}
    </>
  );
}

const InstallPackageLink = ({
  packages,
  children,
}: {
  packages: string[];
  children: React.ReactNode;
}) => {
  const { handleInstallPackages } = useInstallPackages();
  return (
    <button
      onClick={(e) => {
        handleInstallPackages(packages);
        e.preventDefault();
      }}
      className="text-link hover:underline"
      type="button"
    >
      {children}
    </button>
  );
};

/**
 * Replacer that detects pip install commands and renders an install button
 */
export const pipInstallReplacer: Replacer = (domNode: DOMNode) => {
  // Only process text nodes
  if (!(domNode instanceof Text)) {
    return undefined;
  }

  const textContent = cleanAnsiCodes(domNode.data);

  // Quick check to avoid unnecessary regex
  if (!/(pip\s+install|uv\s+add|uv\s+pip\s+install)/i.test(textContent)) {
    return undefined;
  }

  // Find all matches in the text
  const matches: {
    match: RegExpExecArray;
    result: { package: string; endIndex: number };
  }[] = [];

  // Create a new regex for iteration (don't reuse the global one)
  const regex = /(pip\s+install|uv\s+add|uv\s+pip\s+install)\s+/gi;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(textContent)) !== null) {
    const startIndex = match.index;
    const textFromMatch = textContent.slice(startIndex);
    const result = parsePipInstallCommand(textFromMatch);

    if (result) {
      matches.push({ match, result });
    }
  }

  // If no valid matches found, return undefined
  if (matches.length === 0) {
    return undefined;
  }

  // Build the result by splitting text into segments
  const segments: React.ReactNode[] = [];
  let lastIndex = 0;

  matches.forEach((matchInfo, idx) => {
    const { match, result } = matchInfo;
    const startIndex = match.index;
    const endIndex = startIndex + result.endIndex;

    // Add text before this match (with URL processing)
    if (lastIndex < startIndex) {
      const beforeText = textContent.slice(lastIndex, startIndex);
      segments.push(
        <React.Fragment key={`before-${idx}`}>
          {processTextForUrls(beforeText, `before-${idx}`)}
        </React.Fragment>,
      );
    }

    // Add the install button
    const commandText = textContent.slice(startIndex, endIndex);
    segments.push(
      <InstallPackageLink key={`install-${idx}`} packages={[result.package]}>
        {commandText}
      </InstallPackageLink>,
    );

    lastIndex = endIndex;
  });

  // Add any remaining text after the last match
  if (lastIndex < textContent.length) {
    const afterText = textContent.slice(lastIndex);
    segments.push(
      <React.Fragment key="after">
        {processTextForUrls(afterText, "after")}
      </React.Fragment>,
    );
  }

  return <>{segments}</>;
};

/**
 * Replacer that detects URLs in text nodes and makes them clickable
 */
export const urlReplacer: Replacer = (domNode: DOMNode) => {
  // Only process text nodes
  if (!(domNode instanceof Text)) {
    return undefined;
  }

  const textContent = domNode.data;

  // Check if text contains URLs (fast check before parsing)
  if (!/https?:\/\//.test(textContent)) {
    return undefined;
  }

  // Use the shared helper to process URLs
  const result = processTextForUrls(textContent);

  // If no change was made (just plain text), return undefined to let other replacers try
  if (typeof result === "string") {
    return undefined;
  }

  return <>{result}</>;
};

/**
 * Creates a composed replacer function from multiple replacers
 * Replacers are applied in order, and the first one that returns a value wins
 */
export const composeReplacers = (...replacers: Replacer[]): Replacer => {
  return (domNode: DOMNode) => {
    for (const replacer of replacers) {
      const result = replacer(domNode);
      if (result !== undefined) {
        return result;
      }
    }
    return undefined;
  };
};

/**
 * Convert text to React element with ANSI colors and custom replacers applied
 */
export const renderTextWithReplacers = (
  text: string,
  replacer: Replacer,
): React.ReactNode => {
  const html = ansiUp.ansi_to_html(text);

  const content = parse(html, {
    replace: (domNode: DOMNode) => {
      return replacer(domNode);
    },
  });

  return <span>{content}</span>;
};

/**
 * Convert text to React element with ANSI colors, clickable URLs, and pip install buttons
 */
export const RenderTextWithLinks = ({ text }: { text: string }) => {
  const content = useMemo(() => {
    return renderTextWithReplacers(
      text,
      composeReplacers(pipInstallReplacer, urlReplacer),
    );
  }, [text]);

  return <>{content}</>;
};
