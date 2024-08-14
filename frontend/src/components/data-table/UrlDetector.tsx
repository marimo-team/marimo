import React from "react";

export const UrlDetector = ({ text }: { text: string }) => {
  const urlRegex = /(https?:\/\/[^\s]+)/g;

  const createMarkup = (text: string) => {
    const parts = text.split(urlRegex);

    return parts.map((part, index) => {
      if (part.match(urlRegex)) {
        return (
          <a key={index} href={part} target="_blank" rel="noopener noreferrer">
            {part}
          </a>
        );
      }
      return part;
    });
  };

  return <>{createMarkup(text)}</>;
};
