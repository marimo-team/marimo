/* Copyright 2024 Marimo. All rights reserved. */
import { Events } from "@/utils/events";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover";
import { useState } from "react";

const urlRegex = /(https?:\/\/\S+)/;
const imageRegex = /\.(png|jpe?g|gif|webp|svg|ico)(\?.*)?$/i;
const dataImageRegex = /^data:image\//i;
const knownImageDomains = ["avatars.githubusercontent.com"];

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

export type ContentPart =
  | { type: "text"; value: string }
  | { type: "url"; url: string }
  | { type: "image"; url: string };

export function parseContent(text: string): ContentPart[] {
  if (dataImageRegex.test(text)) {
    return [{ type: "image", url: text }];
  }

  const parts = text.split(urlRegex).filter((part) => part.trim() !== "");
  return parts.map((part) => {
    const isUrl = urlRegex.test(part);
    if (isUrl) {
      const isImage =
        imageRegex.test(part) ||
        dataImageRegex.test(part) ||
        knownImageDomains.some((domain) => part.includes(domain));

      if (isImage) {
        return { type: "image", url: part };
      }
      return { type: "url", url: part };
    }
    return { type: "text", value: part };
  });
}

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
