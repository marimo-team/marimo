/* Copyright 2024 Marimo. All rights reserved. */
import { Events } from "@/utils/events";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover";
import { useState } from "react";

const urlRegex = /(https?:\/\/\S+)/g;
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
          className="flex max-h-[80px] overflow-hidden cursor-pointer flex"
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

export const UrlDetector = ({ text }: { text: string }) => {
  if (dataImageRegex.test(text)) {
    return <ImageWithFallback url={text} />;
  }

  const createMarkup = (text: string) => {
    const parts = text.split(urlRegex);

    return parts.map((part, index) => {
      if (urlRegex.test(part)) {
        const isImage =
          imageRegex.test(part) ||
          dataImageRegex.test(part) ||
          knownImageDomains.some((domain) => part.includes(domain));

        if (isImage) {
          return <ImageWithFallback key={index} url={part} />;
        }

        return <URLAnchor key={index} url={part} />;
      }
      return part;
    });
  };

  return <>{createMarkup(text)}</>;
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
