/* Copyright 2024 Marimo. All rights reserved. */
import { cn } from "@/utils/cn";
import { ChevronRightIcon, LoaderCircle, XIcon } from "lucide-react";

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
    <div className="flex gap-1.5 items-center font-bold px-2 py-1.5 text-muted-foreground bg-[var(--slate-2)] text-sm">
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

export const ErrorState: React.FC<{
  error: Error;
  className?: string;
}> = ({ error, className }) => {
  return (
    <div
      className={cn(
        "text-sm bg-red-50 dark:bg-red-900 text-red-600 dark:text-red-50 flex items-center gap-2 p-2 h-8",
        className,
      )}
    >
      <XIcon className="h-4 w-4 mt-0.5" />
      {error.message}
    </div>
  );
};

export const LoadingState: React.FC<{
  message: string;
  className?: string;
}> = ({ message, className }) => {
  return (
    <div
      className={cn(
        "text-sm bg-blue-50 dark:bg-[var(--accent)] text-blue-500 dark:text-blue-50 flex items-center gap-2 p-2 h-8",
        className,
      )}
    >
      <LoaderCircle className="h-4 w-4 animate-spin" />
      {message}
    </div>
  );
};

export const ColumnPreviewContainer: React.FC<{
  children: React.ReactNode;
  className?: string;
}> = ({ children, className }) => {
  return (
    <div className={cn("flex flex-col gap-2 relative", className)}>
      {children}
    </div>
  );
};
