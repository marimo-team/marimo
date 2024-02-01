/* Copyright 2024 Marimo. All rights reserved. */

import { OutputChannel } from "@/core/kernel/messages";
import { cn } from "@/utils/cn";

interface Props {
  text: string;
  channel?: OutputChannel | "stdin";
}

export const TextOutput = ({ text, channel }: Props): JSX.Element => {
  return (
    <span
      className={cn(
        "whitespace-pre",
        channel === "output" && "font-prose",
        channel,
      )}
    >
      {text}
    </span>
  );
};
