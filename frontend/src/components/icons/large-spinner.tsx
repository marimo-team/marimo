/* Copyright 2024 Marimo. All rights reserved. */

import { Loader2Icon } from "lucide-react";
import { useEffect, useState } from "react";
import { cn } from "@/utils/cn";

export const LargeSpinner = ({ title }: { title?: string }) => {
  const [currentTitle, setCurrentTitle] = useState(title);
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    if (title !== currentTitle) {
      setIsVisible(false);
      const timer = setTimeout(() => {
        setCurrentTitle(title);
        setIsVisible(true);
      }, 300); // Wait for fade out animation to complete
      return () => clearTimeout(timer);
    }
  }, [title, currentTitle]);

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
