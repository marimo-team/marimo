/* Copyright 2024 Marimo. All rights reserved. */
import { cn } from "@/utils/cn";
import { ChevronRightIcon } from "lucide-react";

export const RotatingChevron: React.FC<{ isExpanded: boolean }> = ({
  isExpanded,
}) => (
  <ChevronRightIcon
    className={cn("h-3 w-3 transition-transform", isExpanded && "rotate-90")}
  />
);

export const DatasourceLabel: React.FC<{
  children: React.ReactNode;
}> = ({ children }) => {
  return (
    <div className="flex gap-1 items-center font-bold px-2 py-1.5 text-muted-foreground bg-[var(--slate-2)] text-sm">
      {children}
    </div>
  );
};

export const EmptyState: React.FC<{ content: string; className?: string }> = ({
  content,
  className,
}) => {
  return (
    <div className={cn("text-sm text-muted-foreground py-1", className)}>
      {content}
    </div>
  );
};

export const ItemSubtext: React.FC<{ content: string }> = ({ content }) => {
  return (
    <span className="text-xs text-black bg-gray-200 rounded px-1">
      {content}
    </span>
  );
};
