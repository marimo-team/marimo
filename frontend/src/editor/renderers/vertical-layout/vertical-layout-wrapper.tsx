/* Copyright 2023 Marimo. All rights reserved. */
import { PropsWithChildren } from "react";
import { cn } from "@/lib/utils";
import { AppConfig } from "@/core/config/config";

interface Props {
  appConfig: AppConfig;
  invisible?: boolean;
}

export const VerticalLayoutWrapper: React.FC<PropsWithChildren<Props>> = ({
  invisible,
  appConfig,
  children,
}) => {
  return (
    <div className="sm:px-16 md:px-32">
      <div
        className={cn(
          "m-auto pb-12",
          appConfig.width !== "full" && "max-w-contentWidth min-w-[400px]",
          // Hide the cells for a fake loading effect, to avoid flickering
          invisible && "invisible"
        )}
      >
        {children}
      </div>
    </div>
  );
};
