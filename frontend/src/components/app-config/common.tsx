/* Copyright 2024 Marimo. All rights reserved. */
import { cn } from "@/utils/cn";
import type { HTMLProps, PropsWithChildren } from "react";

export const SettingTitle: React.FC<PropsWithChildren> = ({ children }) => {
  return (
    <div className="text-md font-semibold text-muted-foreground uppercase tracking-wide  mb-1">
      {children}
    </div>
  );
};

export const SettingSubtitle: React.FC<HTMLProps<HTMLDivElement>> = ({
  children,
  className,
  ...props
}) => {
  return (
    <div
      {...props}
      className={cn(
        "text-base font-semibold underline-offset-2 text-accent-foreground uppercase tracking-wide",
        className,
      )}
    >
      {children}
    </div>
  );
};

export const SettingDescription: React.FC<PropsWithChildren> = ({
  children,
}) => {
  return <p className="text-sm text-muted-foreground">{children}</p>;
};
