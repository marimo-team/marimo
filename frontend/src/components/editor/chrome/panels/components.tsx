/* Copyright 2026 Marimo. All rights reserved. */

import * as React from "react";
import {
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/utils/cn";
import { SparklesIcon } from "lucide-react";
import { Tooltip } from "@/components/ui/tooltip";
import type { DataSourceDiscoveryGroup } from "@/core/datasets/data-source-discovery";

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

const DiscoveredSourcesBadge = ({
  count,
  type,
}: {
  count: number;
  type: DataSourceDiscoveryGroup;
}) => {
  if (count === 0) {
    return null;
  }

  let noun: string;
  if (type === "database") {
    noun = count === 1 ? "database" : "databases";
  } else {
    noun = count === 1 ? "remote storage" : "remote storages";
  }
  const content = `${count} ${noun} detected in your environment, ready to quick-add`;

  return (
    <Tooltip content={content}>
      <span>
        <PanelBadge className="gap-0.5 border-(--blue-6) bg-(--blue-3) text-(--blue-11) hover:bg-(--blue-4) dark:border-(--blue-8) dark:bg-(--blue-3) dark:hover:bg-(--blue-4)">
          <SparklesIcon className="h-2.5 w-2.5" />
          {count}
        </PanelBadge>
      </span>
    </Tooltip>
  );
};

export {
  PanelAccordionItem,
  PanelAccordionTrigger,
  PanelAccordionContent,
  PanelBadge,
  DiscoveredSourcesBadge,
};
