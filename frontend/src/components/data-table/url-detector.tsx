/* Copyright 2026 Marimo. All rights reserved. */

import { marked } from "marked";
import { Fragment, type ReactNode, useState } from "react";
import { MarkdownRenderer } from "@/components/markdown/markdown-renderer";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Events } from "@/utils/events";
import type { ContentPart } from "@/utils/url-parser";
import { findMatchRanges, highlightRanges } from "./search-highlight";

const ImageWithFallback = ({
  url,
  fallbackLabel,
}: {
  url: string;
  fallbackLabel?: ReactNode;
}) => {
  const [error, setError] = useState(false);
  const [open, setOpen] = useState(false);

  if (error) {
    return <URLAnchor url={url}>{fallbackLabel}</URLAnchor>;
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild={true}>
        <div
          className="flex max-h-[80px] overflow-hidden cursor-pointer"
          onMouseEnter={() => setOpen(true)}
          onMouseLeave={() => setOpen(false)}
        >
          <img
            src={url}
            alt="URL preview"
            className="object-contain rounded max-h-[80px]"
            onError={() => setError(true)}
          />
        </div>
      </PopoverTrigger>

      <PopoverContent
        className="z-50 p-2 bg-popover rounded-md shadow-lg border w-fit"
        align="start"
        side="right"
      >
        <img
          src={url}
          alt="URL preview"
          className="object-contain max-h-[500px] rounded"
          onError={() => setError(true)}
        />
      </PopoverContent>
    </Popover>
  );
};

export function isMarkdown(text: string): boolean {
  const tokens = marked.lexer(text);

  const commonMarkdownIndicators = new Set([
    "space",
    "code",
    "fences",
    "heading",
    "hr",
    "link",
    "blockquote",
    "list",
    "html",
    "def",
    "table",
    "lheading",
    "escape",
    "tag",
    "reflink",
    "strong",
    "codespan",
    "url",
  ]);

  return tokens.some((token) => commonMarkdownIndicators.has(token.type));
}

// Wrapper component so that we call isMarkdown only on trigger
export const MarkdownUrlDetector = ({
  content,
  parts,
}: {
  content: string;
  parts: ContentPart[];
}) => {
  if (isMarkdown(content)) {
    return <MarkdownRenderer content={content} />;
  }
  return <UrlDetector parts={parts} />;
};

export const UrlDetector = ({
  parts,
  highlightPattern,
}: {
  parts: ContentPart[];
  highlightPattern?: RegExp;
}) => {
  // Match against the whole string so a query that spans a text part and
  // a link is still marked. Each part then takes its slice of the ranges.
  const ranges = highlightPattern
    ? findMatchRanges(parts.map(partText).join(""), highlightPattern)
    : [];

  let offset = 0;
  const markup = parts.map((part, idx) => {
    const text = partText(part);
    const label = highlightRanges(text, ranges, offset);
    offset += text.length;

    if (part.type === "url") {
      return (
        <URLAnchor key={idx} url={part.url}>
          {label}
        </URLAnchor>
      );
    }
    if (part.type === "image") {
      return (
        <ImageWithFallback key={idx} url={part.url} fallbackLabel={label} />
      );
    }
    return <Fragment key={idx}>{label}</Fragment>;
  });

  return markup;
};

function partText(part: ContentPart): string {
  return part.type === "text" ? part.value : part.url;
}

const URLAnchor = ({
  url,
  children,
}: {
  url: string;
  children?: ReactNode;
}) => {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      onClick={Events.stopPropagation()}
      className="text-link hover:underline"
    >
      {children ?? url}
    </a>
  );
};
