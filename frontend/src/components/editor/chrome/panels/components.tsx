/* Copyright 2026 Marimo. All rights reserved. */

import * as React from "react";
import {
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/utils/cn";

/**
 * Styled AccordionItem for sidebar panels.
 * Applies border-b by default; set `lastItem` to remove it on the final item.
 */
const PanelAccordionItem = React.forwardRef<
  React.ComponentRef<typeof AccordionItem>,
  React.ComponentPropsWithoutRef<typeof AccordionItem> & {
    lastItem?: boolean;
  }
>(({ className, lastItem, ...props }, ref) => (
  <AccordionItem
    ref={ref}
    className={cn(lastItem && "border-b-0", className)}
    {...props}
  />
));
PanelAccordionItem.displayName = "PanelAccordionItem";

/**
 * Styled AccordionTrigger for sidebar panels.
 * Applies compact uppercase styling and wraps children in a flex container
 * with gap for icon + label layout.
 */
const PanelAccordionTrigger = React.forwardRef<
  React.ComponentRef<typeof AccordionTrigger>,
  React.ComponentPropsWithoutRef<typeof AccordionTrigger>
>(({ className, children, ...props }, ref) => (
  <AccordionTrigger
    ref={ref}
    className={cn(
      "px-3 py-2 text-xs font-semibold uppercase tracking-wide hover:no-underline",
      className,
    )}
    {...props}
  >
    <span className="flex items-center gap-2">{children}</span>
  </AccordionTrigger>
));
PanelAccordionTrigger.displayName = "PanelAccordionTrigger";

/**
 * Styled AccordionContent for sidebar panels.
 * Removes default wrapper padding.
 */
const PanelAccordionContent = React.forwardRef<
  React.ComponentRef<typeof AccordionContent>,
  React.ComponentPropsWithoutRef<typeof AccordionContent>
>(({ wrapperClassName, ...props }, ref) => (
  <AccordionContent
    ref={ref}
    wrapperClassName={cn("p-0", wrapperClassName)}
    {...props}
  />
));
PanelAccordionContent.displayName = "PanelAccordionContent";

/**
 * Styled Badge for sidebar panels.
 */
const PanelBadge = ({
  className,
  ...props
}: React.ComponentPropsWithoutRef<typeof Badge>) => (
  <Badge
    variant="secondary"
    className={cn("py-0 px-1.5 text-[10px]", className)}
    {...props}
  />
);
PanelBadge.displayName = "PanelBadge";

export {
  PanelAccordionItem,
  PanelAccordionTrigger,
  PanelAccordionContent,
  PanelBadge,
};
