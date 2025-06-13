/* Copyright 2024 Marimo. All rights reserved. */
import type { PropsWithChildren } from "react";
import type { AppConfig } from "@/core/config/config-schema";
import { cn } from "@/utils/cn";

interface Props {
  className?: string;
  innerClassName?: string;
  appConfig: AppConfig;
  invisible?: boolean;
}

export const VerticalLayoutWrapper: React.FC<PropsWithChildren<Props>> = ({
  invisible,
  appConfig,
  className,
  children,
  innerClassName,
}) => {
  return (
    <div
      className={cn(
        "px-1 sm:px-16 md:px-20 xl:px-24 print:px-0 print:pb-0",
        className,
      )}
    >
      <div
        className={cn(
          // Large mobile bottom padding due to mobile browser navigation bar
          "m-auto pb-24 sm:pb-12",
          appConfig.width === "compact" && "max-w-contentWidth min-w-[400px]",
          appConfig.width === "medium" &&
            "max-w-contentWidthMedium min-w-[400px]",
          appConfig.width === "columns" && "w-fit",
          appConfig.width === "full" && "max-w-full",
          // Hide the cells for a fake loading effect, to avoid flickering
          invisible && "invisible",
          innerClassName,
        )}
      >
        {children}
      </div>
    </div>
  );
};
