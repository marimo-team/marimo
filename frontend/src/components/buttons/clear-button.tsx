/* Copyright 2024 Marimo. All rights reserved. */

import { cn } from "@/utils/cn";

interface ClearButtonProps {
  className?: string;
  dataTestId?: string;
  onClick: () => void;
}

export const ClearButton: React.FC<ClearButtonProps> = (props) => (
  <button
    type="button"
    data-testid={props.dataTestId}
    className={cn(
      "text-xs font-semibold text-accent-foreground",
      props.className,
    )}
    onClick={props.onClick}
  >
    Clear
  </button>
);
