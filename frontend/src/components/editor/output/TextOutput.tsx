/* Copyright 2024 Marimo. All rights reserved. */

import { OutputChannel } from "@/core/kernel/messages";
import { cn } from "@/utils/cn";
import { AnsiUp } from "ansi_up";

const ansiUp = new AnsiUp();

interface Props {
  text: string;
  channel?: OutputChannel | "stdin";
}

export const TextOutput = ({ text, channel }: Props): JSX.Element => {
  const shouldRenderAnsi = channel === "stdout";

  const renderAnsiText = (text: string) => {
    return (
      <span dangerouslySetInnerHTML={{ __html: ansiUp.ansi_to_html(text) }} />
    );
  };

  return (
    <span
      className={cn(
        "whitespace-pre",
        channel === "output" && "font-prose",
        channel,
      )}
    >
      {shouldRenderAnsi ? renderAnsiText(text) : text}
    </span>
  );
};
