/* Copyright 2024 Marimo. All rights reserved. */
import { Label } from "@/components/ui/label";
import { renderHTML } from "@/plugins/core/RenderHTML";
import React, { PropsWithChildren } from "react";
import { cn } from "@/utils/cn";

interface Props {
  label: string | null | undefined;
  className?: string;
  labelClassName?: string;
  id?: string;
  fullWidth?: boolean;
  /**
   * Align the label to the top, left, or right of the component.
   * @default "left"
   */
  align?: "top" | "left" | "right";
}

/**
 * Label a component.
 */
export const Labeled: React.FC<PropsWithChildren<Props>> = ({
  label,
  children,
  align = "left",
  className,
  labelClassName,
  fullWidth,
  id,
}) => {
  // If fullWidth is true, force align to be "top"
  if (fullWidth) {
    align = "top";
  }
  if (!label) {
    // If its a top label, just return the children
    if (align === "top") {
      return children;
    }
    // Otherwise, return the children in an inline-flex container
    return <div className={cn("inline-flex", className)}>{children}</div>;
  }

  const labelElement = (
    <Label htmlFor={id} className={cn("font-prose", labelClassName)}>
      {renderHTML({ html: label })}
    </Label>
  );

  return (
    <div
      className={cn(
        "mo-label inline-flex",
        "pt-0 pb-0 pl-0",
        align === "top" && "flex-col items-start gap-y-2",
        align === "left" && "flex-row items-center gap-x-1.5 pr-2",
        align === "right" && "flex-row-reverse items-center gap-x-1.5 pr-2",
        fullWidth && "block space-y-2",
        className,
      )}
    >
      {labelElement}
      {children}
    </div>
  );
};
