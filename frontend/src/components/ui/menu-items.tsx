/* Copyright 2024 Marimo. All rights reserved. */
import { cn } from "@/utils/cn";
import { cva } from "class-variance-authority";
import React from "react";

export const menuContentCommon = cva(
  "z-50 min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md",
  {
    variants: {
      subcontent: {
        true: "shadow-lg",
      },
    },
  },
);

export const menuSubTriggerVariants = cva(
  "flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none focus:bg-accent focus:text-accent-foreground data-[state=open]:bg-accent data-[state=open]:text-accent-foreground",
  {
    variants: {
      inset: {
        true: "pl-8",
      },
    },
  },
);

export const MENU_ITEM_DISABLED =
  "data-[disabled]:pointer-events-none data-[disabled]:opacity-50";

export const menuControlVariants = cva(
  cn(
    "relative flex cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground",
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
    "menu-item relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none",
    MENU_ITEM_DISABLED,
  ),
  {
    variants: {
      inset: {
        true: "pl-8",
      },
      variant: {
        default:
          "focus:bg-accent focus:text-accent-foreground aria-selected:bg-accent aria-selected:text-accent-foreground",
        danger:
          "focus:bg-[var(--red-5)] focus:text-[var(--red-12)] aria-selected:bg-[var(--red-5)] aria-selected:text-[var(--red-12)]",
        muted:
          "focus:bg-muted/70 focus:text-muted-foreground aria-selected:bg-muted/70 aria-selected:text-muted-foreground",
        success:
          "focus:bg-[var(--grass-3)] focus:text-[var(--grass-11)] aria-selected:bg-[var(--grass-3)] aria-selected:text-[var(--grass-11)]",
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
