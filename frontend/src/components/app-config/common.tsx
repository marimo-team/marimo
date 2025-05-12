/* Copyright 2024 Marimo. All rights reserved. */
import { cn } from "@/utils/cn";
import type { HTMLProps, PropsWithChildren } from "react";
import type { SqlOutputType } from "@/core/config/config-schema";

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

export const SQL_OUTPUT_SELECT_OPTIONS: Array<{
  label: string;
  value: SqlOutputType;
}> = [
  { label: "Auto (Default)", value: "auto" },
  { label: "Native", value: "native" },
  { label: "Polars", value: "polars" },
  { label: "Lazy Polars", value: "lazy-polars" },
  { label: "Pandas", value: "pandas" },
];
