/* Copyright 2024 Marimo. All rights reserved. */
import { Loader2Icon } from "lucide-react";

export const LargeSpinner = () => {
  return (
    <div className="flex flex-col h-full flex-1 items-center justify-center p-4">
      <Loader2Icon
        className="size-20 animate-spin text-primary"
        strokeWidth={1}
      />
      <div className="mt-2 text-muted-foreground font-semibold text-lg">
        Initializing...
      </div>
    </div>
  );
};
