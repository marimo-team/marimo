/* Copyright 2023 Marimo. All rights reserved. */
import React from "react";

interface Props {
  code: string;
}

export const TinyCode: React.FC<Props> = ({ code }) => {
  return (
    <div
      className="text-gray-500 flex flex-col overflow-hidden"
      style={{
        fontSize: "8px",
        lineHeight: "10px",
      }}
    >
      {code
        .trim()
        .split("\n")
        .map((line, idx) => {
          return (
            <code className="whitespace-pre min-h-[10px]" key={idx}>
              {line}
            </code>
          );
        })}
    </div>
  );
};
