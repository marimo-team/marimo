/* Copyright 2024 Marimo. All rights reserved. */
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/utils/cn";
import type React from "react";
import type { PropsWithChildren } from "react";

export const FooterItem: React.FC<
  PropsWithChildren<
    {
      selected: boolean;
      tooltip: React.ReactNode;
    } & React.HTMLAttributes<HTMLDivElement>
  >
> = ({ children, tooltip, selected, className, ...rest }) => {
  const content = (
    <div
      className={cn(
        "h-full flex items-center p-2 text-sm shadow-inset font-mono cursor-pointer rounded",
        !selected && "hover:bg-[var(--sage-3)]",
        selected && "bg-[var(--sage-4)]",
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );

  if (tooltip) {
    return (
      <Tooltip content={tooltip} side="top" delayDuration={200}>
        {content}
      </Tooltip>
    );
  }

  return content;
};
