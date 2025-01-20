/* Copyright 2024 Marimo. All rights reserved. */
import { Events } from "@/utils/events";
import { useState } from "react";

const urlRegex = /(https?:\/\/\S+)/g;
const imageRegex = /\.(png|jpe?g|gif|webp|svg|ico)(\?.*)?$/i;
const knownImageDomains = ["avatars.githubusercontent.com"];

const ImageWithFallback = ({ url }: { url: string }) => {
  const [error, setError] = useState(false);

  if (error) {
    return <URLAnchor url={url} />;
  }

  return (
    <div className="flex max-h-[20px] overflow-hidden">
      <img
        src={url}
        alt="URL preview"
        className="object-contain max-h-full max-w-full rounded"
        onError={() => setError(true)}
      />
    </div>
  );
};

export const UrlDetector = ({ text }: { text: string }) => {
  const createMarkup = (text: string) => {
    const parts = text.split(urlRegex);

    return parts.map((part, index) => {
      if (urlRegex.test(part)) {
        const isImage =
          imageRegex.test(part) ||
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
