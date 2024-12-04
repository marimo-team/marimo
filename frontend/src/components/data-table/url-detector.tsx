/* Copyright 2024 Marimo. All rights reserved. */
import { Events } from "@/utils/events";

const urlRegex = /(https?:\/\/\S+)/g;
export const UrlDetector = ({ text }: { text: string }) => {
  const createMarkup = (text: string) => {
    const parts = text.split(urlRegex);

    return parts.map((part, index) => {
      if (urlRegex.test(part)) {
        return (
          <a
            key={index}
            href={part}
            target="_blank"
            rel="noopener noreferrer"
            onClick={Events.stopPropagation()}
            className="text-link hover:underline"
          >
            {part}
          </a>
        );
      }
      return part;
    });
  };

  return <>{createMarkup(text)}</>;
};
