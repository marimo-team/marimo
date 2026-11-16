/* Copyright 2026 Marimo. All rights reserved. */

import { Loader2Icon } from "lucide-react";
import { useDebounce } from "@/hooks/useDebounce";
import { cn } from "@/utils/cn";

export const LargeSpinner = ({ title }: { title?: string }) => {
  const currentTitle = useDebounce(title, 300);
  const isVisible = title === currentTitle;

  return (
    <div className="flex flex-col h-full flex-1 items-center justify-center p-4">
      <Loader2Icon
        className="size-20 animate-spin text-primary"
        data-testid="large-spinner"
        strokeWidth={1}
      />
      <div
        className={cn(
          "mt-2 text-muted-foreground font-semibold text-lg transition-opacity duration-300",
          isVisible ? "opacity-100" : "opacity-0",
        )}
      >
        {currentTitle}
      </div>
    </div>
  );
};
