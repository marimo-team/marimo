/* Copyright 2024 Marimo. All rights reserved. */

import { ChartPieIcon, Loader2 } from "lucide-react";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { cn } from "@/utils/cn";

export const ChartLoadingState: React.FC = () => (
  <div className="flex items-center gap-2 justify-center">
    <Loader2 className="w-10 h-10 animate-spin" strokeWidth={1} />
    <span>Loading chart...</span>
  </div>
);

export const ChartErrorState: React.FC<{ error: Error }> = ({ error }) => (
  <div className="flex items-center justify-center">
    <ErrorBanner error={error} />
  </div>
);

export const ChartInfoState: React.FC<{
  children: React.ReactNode;
  className?: string;
}> = ({ children, className }) => {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-4",
        className,
      )}
    >
      <ChartPieIcon className="w-10 h-10 text-muted-foreground" />
      <span className="text-md font-semibold text-muted-foreground">
        {children}
      </span>
    </div>
  );
};
