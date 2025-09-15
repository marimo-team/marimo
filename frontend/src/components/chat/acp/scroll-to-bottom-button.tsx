/* Copyright 2024 Marimo. All rights reserved. */

import { ArrowDownIcon } from "lucide-react";
import { memo } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";

interface ScrollToBottomButtonProps {
  isVisible: boolean;
  onScrollToBottom: () => void;
  className?: string;
}

const ScrollToBottomButton = memo<ScrollToBottomButtonProps>(
  ({ isVisible, onScrollToBottom, className }) => {
    if (!isVisible) {
      return null;
    }

    return (
      <div
        className={cn(
          "absolute bottom-2 right-6 z-10 animate-in fade-in-0 zoom-in-95 duration-200",
          className,
        )}
      >
        <Button
          variant="secondary"
          size="sm"
          onClick={onScrollToBottom}
          className={cn(
            "h-8 w-8 p-0 rounded-full",
            "bg-background/90 backdrop-blur-sm",
            "border border-border/50",
            "shadow-md shadow-black/10",
            "hover:bg-background hover:shadow-black/15",
            "transition-all duration-200",
            "focus:outline-none focus:ring-2 focus:ring-primary/50",
          )}
        >
          <ArrowDownIcon className="h-4 w-4" />
          <span className="sr-only">Scroll to bottom</span>
        </Button>
      </div>
    );
  },
);
ScrollToBottomButton.displayName = "ScrollToBottomButton";

export default ScrollToBottomButton;
