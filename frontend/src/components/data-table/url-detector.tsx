/* Copyright 2024 Marimo. All rights reserved. */

import { marked } from "marked";
import { useState } from "react";
import { MarkdownRenderer } from "@/components/markdown/markdown-renderer";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Events } from "@/utils/events";
import type { ContentPart } from "@/utils/url-parser";

const ImageWithFallback = ({ url }: { url: string }) => {
  const [error, setError] = useState(false);
  const [open, setOpen] = useState(false);

  if (error) {
    return <URLAnchor url={url} />;
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

export const UrlDetector = ({ parts }: { parts: ContentPart[] }) => {
  const markup = parts.map((part, idx) => {
    if (part.type === "url") {
      return <URLAnchor key={idx} url={part.url} />;
    }
    if (part.type === "image") {
      return <ImageWithFallback key={idx} url={part.url} />;
    }
    return part.value;
  });

  return markup;
};

const URLAnchor = ({ url }: { url: string }) => {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      onClick={Events.stopPropagation()}
      className="text-link hover:underline"
    >
      {url}
    </a>
  );
};
