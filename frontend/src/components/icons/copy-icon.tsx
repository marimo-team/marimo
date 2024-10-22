/* Copyright 2024 Marimo. All rights reserved. */
import { CheckIcon, Copy } from "lucide-react";
import type React from "react";
import { useState } from "react";
import { Tooltip } from "../ui/tooltip";
import { cn } from "@/utils/cn";
import { Events } from "@/utils/events";

interface Props {
  value: string;
  className?: string;
  tooltip?: string | false;
}

export const CopyClipboardIcon: React.FC<Props> = ({
  value,
  className,
  tooltip,
}) => {
  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = Events.stopPropagation(() => {
    navigator.clipboard.writeText(value).then(() => {
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    });
  });

  const button = (
    <span onClick={handleCopy}>
      {isCopied ? (
        <CheckIcon className={cn(className, "text-[var(--grass-11)]")} />
      ) : (
        <Copy className={className} />
      )}
    </span>
  );

  if (tooltip === false) {
    return button;
  }

  return (
    <Tooltip
      content={isCopied ? "Copied!" : (tooltip ?? "Copy to clipboard")}
      delayDuration={400}
    >
      {button}
    </Tooltip>
  );
};
