/* Copyright 2024 Marimo. All rights reserved. */
import { ChevronLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";

interface SidebarToggleProps {
  isOpen: boolean;
  toggle: () => void;
}

export const SidebarToggle = ({ isOpen, toggle }: SidebarToggleProps) => {
  return (
    <div className="invisible lg:visible absolute top-[12px] -right-[16px] z-20 bg-white dark:bg-primary-foreground">
      <Button
        onClick={toggle}
        className="rounded-md w-8 h-8"
        variant="outline"
        size="icon"
      >
        <ChevronLeft
          className={cn(
            "h-4 w-4 transition-transform ease-in-out duration-700",
            isOpen ? "rotate-0" : "rotate-180",
          )}
        />
      </Button>
    </div>
  );
};
