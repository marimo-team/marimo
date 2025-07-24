/* Copyright 2024 Marimo. All rights reserved. */

import { AnsiUp } from "ansi_up";
import type { JSX } from "react";
import type { OutputChannel } from "@/core/kernel/messages";
import { cn } from "@/utils/cn";

const ansiUp = new AnsiUp();

interface Props {
  text: string;
  channel?: OutputChannel;
  wrapText?: boolean;
}

export const TextOutput = ({ text, channel, wrapText }: Props): JSX.Element => {
  const shouldRenderAnsi = channel === "stdout" || channel === "stderr";

  const renderAnsiText = (text: string) => {
    return (
      <span
        className={
          wrapText ? "whitespace-pre-wrap break-words" : "whitespace-pre"
        }
        dangerouslySetInnerHTML={{ __html: ansiUp.ansi_to_html(text) }}
      />
    );
  };

  return (
    <span
      className={cn(
        !shouldRenderAnsi &&
          (wrapText ? "whitespace-pre-wrap break-words" : "whitespace-pre"),
        channel === "output" && "font-prose",
        channel,
      )}
    >
      {shouldRenderAnsi ? renderAnsiText(text) : text}
    </span>
  );
};
