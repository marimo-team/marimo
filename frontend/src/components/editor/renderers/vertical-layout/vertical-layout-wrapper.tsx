/* Copyright 2024 Marimo. All rights reserved. */
import { PropsWithChildren } from "react";
import { cn } from "@/utils/cn";
import { AppConfig } from "@/core/config/config-schema";

interface Props {
  className?: string;
  appConfig: AppConfig;
  invisible?: boolean;
}

export const VerticalLayoutWrapper: React.FC<PropsWithChildren<Props>> = ({
  invisible,
  appConfig,
  className,
  children,
}) => {
  return (
    <div className={cn("px-1 sm:px-16 md:px-32", className)}>
      <div
        className={cn(
          // Large mobile bottom padding due to mobile browser navigation bar
          "m-auto pb-24 sm:pb-12",
          appConfig.width === "normal" && "max-w-contentWidth min-w-[400px]",
          appConfig.width === "medium" &&
            "max-w-contentWidthMedium min-w-[400px]",
          // Hide the cells for a fake loading effect, to avoid flickering
          invisible && "invisible",
        )}
      >
        {children}
      </div>
    </div>
  );
};
