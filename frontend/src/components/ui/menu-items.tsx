/* Copyright 2026 Marimo. All rights reserved. */

import { cva } from "class-variance-authority";
import React from "react";
import { cn } from "@/utils/cn";

export const menuContentCommon = cva(
  "z-50 min-w-32 overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md forced-color-adjust-none forced-colors:border-[CanvasText] forced-colors:bg-[Canvas] forced-colors:text-[CanvasText]",
  {
    variants: {
      subcontent: {
        true: "shadow-lg",
      },
    },
  },
);

export const menuSubTriggerVariants = cva(
  "flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-hidden data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground data-[state=open]:bg-accent data-[state=open]:text-accent-foreground forced-color-adjust-none forced-colors:data-[highlighted]:bg-[Highlight] forced-colors:data-[highlighted]:text-[HighlightText] forced-colors:data-[state=open]:bg-[Highlight] forced-colors:data-[state=open]:text-[HighlightText]",
  {
    variants: {
      inset: {
        true: "pl-8",
      },
    },
  },
);

export const MENU_ITEM_DISABLED =
  "data-disabled:pointer-events-none data-disabled:opacity-50 forced-colors:data-disabled:text-[GrayText]";

export const menuControlVariants = cva(
  cn(
    "relative flex cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-hidden transition-colors data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground forced-color-adjust-none forced-colors:data-[highlighted]:bg-[Highlight] forced-colors:data-[highlighted]:text-[HighlightText]",
    MENU_ITEM_DISABLED,
  ),
  { variants: {} },
);

export const menuControlCheckVariants = cva(
  "absolute left-2 flex h-3.5 w-3.5 items-center justify-center",
  {
    variants: {},
  },
);

export const menuLabelVariants = cva("px-2 py-1.5 text-sm font-semibold", {
  variants: {
    inset: {
      true: "pl-8",
    },
  },
});

export const menuItemVariants = cva(
  cn(
    "menu-item relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-hidden forced-color-adjust-none forced-colors:data-[highlighted]:bg-[Highlight] forced-colors:data-[highlighted]:text-[HighlightText] forced-colors:aria-selected:bg-[Highlight] forced-colors:aria-selected:text-[HighlightText]",
    MENU_ITEM_DISABLED,
  ),
  {
    variants: {
      inset: {
        true: "pl-8",
      },
      variant: {
        default:
          "data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground aria-selected:bg-accent aria-selected:text-accent-foreground",
        danger:
          "data-[highlighted]:bg-(--red-5) data-[highlighted]:text-(--red-12) aria-selected:bg-(--red-5) aria-selected:text-(--red-12)",
        muted:
          "data-[highlighted]:bg-muted/70 data-[highlighted]:text-muted-foreground aria-selected:bg-muted/70 aria-selected:text-muted-foreground",
        success:
          "data-[highlighted]:bg-(--grass-3) data-[highlighted]:text-(--grass-11) aria-selected:bg-(--grass-3) aria-selected:text-(--grass-11)",
        disabled: "text-muted-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export const menuSeparatorVariants = cva(
  "-mx-1 my-1 h-px bg-border last:hidden",
  {
    variants: {},
  },
);

export const MenuShortcut = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement>) => {
  return (
    <span
      className={cn("ml-auto text-xs tracking-widest opacity-60", className)}
      {...props}
    />
  );
};
MenuShortcut.displayName = "MenuShortcut";
